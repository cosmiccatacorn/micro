"""
Reconocimiento en vivo de ambas manos:
- Mano Derecha: Gestos 1-5.
- Mano Izquierda: Gesto de pinza (índice y pulgar), mapeado de 0% a 100%.
Envía la información por puerto serial (pyserial).

Protocolo Serial:
    Se envía "N,P\n" (N = 0..5 para la derecha, P = 0..100 para la izquierda).
    Ejemplo: "3,85\n" significa 3 dedos derechos y 85% de apertura en la pinza izquierda.

Dependencias:
    pip install opencv-python mediapipe pyserial

Uso:
    python gestos_manos.py --listar
    python gestos_manos.py --puerto COM3
"""

import argparse
import math
import time
from collections import Counter, deque

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import serial
import serial.tools.list_ports

# Índices de landmarks
WRIST = 0
INDEX_MCP = 5
THUMB_TIP, THUMB_IP = 4, 3
INDEX_TIP = 8
PINKY_MCP = 17
FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]  # (punta, PIP)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),  # pulgar
    (5, 6), (6, 7), (7, 8),  # índice
    (9, 10), (10, 11), (11, 12),  # medio
    (13, 14), (14, 15), (15, 16),  # anular
    (17, 18), (18, 19), (19, 20),  # meñique
    (0, 5), (5, 9), (9, 13), (13, 17), (0, 17)  # palma
]


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def contar_dedos_derecha(lm):
    total = 0
    if dist(lm[THUMB_TIP], lm[PINKY_MCP]) > dist(lm[THUMB_IP], lm[PINKY_MCP]):
        total += 1
    for tip, pip in FINGERS:
        if dist(lm[tip], lm[WRIST]) > dist(lm[pip], lm[WRIST]):
            total += 1
    return total


def calcular_porcentaje_pinza_izquierda(lm):
    d_pinza = dist(lm[THUMB_TIP], lm[INDEX_TIP])
    d_ref = dist(lm[WRIST], lm[INDEX_MCP])  # Referencia de escala para invarianza de distancia

    if d_ref == 0:
        return 0

    ratio = d_pinza / d_ref

    # Valores empíricos: ~0.2 es cerrado, ~1.0 es completamente abierto
    min_ratio, max_ratio = 0.2, 1.0
    porcentaje = (ratio - min_ratio) / (max_ratio - min_ratio) * 100
    return max(0, min(100, int(porcentaje)))


def dibujar_landmarks(imagen, landmarks, color_nodos=(0, 0, 255)):
    h, w, _ = imagen.shape
    puntos = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for c in HAND_CONNECTIONS:
        cv2.line(imagen, puntos[c[0]], puntos[c[1]], (0, 255, 0), 2)
    for pt in puntos:
        cv2.circle(imagen, pt, 4, color_nodos, -1)


def listar_puertos():
    puertos = list(serial.tools.list_ports.comports())
    if not puertos:
        print("No se encontraron puertos seriales.")
    for p in puertos:
        print(f"{p.device}\n{p.description}")


def abrir_serial(puerto, baud):
    try:
        ser = serial.Serial(puerto, baud, timeout=0.1)
        time.sleep(2)
        print(f"Serial abierto: {puerto} @ {baud} baudios")
        return ser
    except serial.SerialException as e:
        raise SystemExit(f"No se pudo abrir {puerto}: {e}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", help="Ej: COM3 o /dev/ttyUSB0", default="COM6")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--listar", action="store_true", help="Lista puertos y sale")
    ap.add_argument("--modelo", type=str, default="hand_landmarker.task", help="Ruta al modelo .task")
    args = ap.parse_args()

    if args.listar:
        listar_puertos()
        return

    ser = abrir_serial(args.puerto, args.baud) if args.puerto else None
    cap = cv2.VideoCapture(args.camara)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir la cámara.")

    # Colas para estabilizar lecturas
    historial_der = deque(maxlen=10)
    historial_izq = deque(maxlen=10)

    ultimo_der_enviado = -1
    ultimo_izq_enviado = -1

    base_options = python.BaseOptions(model_asset_path=args.modelo)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.7,
        min_tracking_confidence=0.6
    )

    start_time = time.perf_counter()

    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok: break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.perf_counter() - start_time) * 1000)
                resultado = landmarker.detect_for_video(mp_image, timestamp_ms)

                num_der = 0
                pct_izq = 0

                if resultado.hand_landmarks:
                    for lm_hand, handedness in zip(resultado.hand_landmarks, resultado.handedness):
                        categoria = handedness[0].category_name

                        if categoria == "Right":
                            dibujar_landmarks(frame, lm_hand, (255, 0, 0))  # Nodos azules
                            n = contar_dedos_derecha(lm_hand)
                            num_der = n if 1 <= n <= 5 else 0
                        elif categoria == "Left":
                            dibujar_landmarks(frame, lm_hand, (0, 0, 255))  # Nodos rojos
                            pct_izq = calcular_porcentaje_pinza_izquierda(lm_hand)

                # Estabilización de datos
                historial_der.append(num_der)
                historial_izq.append(pct_izq)

                estable_der = Counter(historial_der).most_common(1)[0][0]
                # Media móvil para suavizar el porcentaje
                estable_izq = int(sum(historial_izq) / len(historial_izq)) if historial_izq else 0

                # Lógica de envío: Enviar si el número derecho cambia o la pinza varía al menos un 5%
                listos_para_evaluar = len(historial_der) == historial_der.maxlen
                cambio_significativo = (estable_der != ultimo_der_enviado) or (
                            abs(estable_izq - ultimo_izq_enviado) >= 5)

                if listos_para_evaluar and cambio_significativo:
                    msg = f"{estable_der},{estable_izq}"
                    print(f"{msg}")
                    if ser:
                        try:
                            ser.write(f"{msg}\n".encode("ascii"))
                        except serial.SerialException as e:
                            print(f"Error serial: {e}")
                            ser = None
                    ultimo_der_enviado = estable_der
                    ultimo_izq_enviado = estable_izq

                # HUD en pantalla
                cv2.putText(frame, f"Derecha (Pinza): {estable_izq}%", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, f"Izquierda (Num): {estable_der}", (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)

                estado = f"Serial: {args.puerto}@{args.baud}" if ser else "Serial: desconectado"
                cv2.putText(frame, estado, (20, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

                cv2.imshow("Gestos Manos", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser:
            ser.close()


if __name__ == "__main__":
    main()