#!/usr/bin/env python3
"""Verify that an image contains a full face (hairline->neck) using MediaPipe FaceMesh.

This is a *verification* helper (not a cropper): it returns success/failure and
simple diagnostics.

Usage:
  . <HOME>/.openclaw/workspace/.venv-idocr/bin/activate
  python3 mediapipe_facecheck.py --input face.jpg

Exit codes:
  0 ok (mouth + chin present with margin)
  2 no face landmarks detected
  3 face detected but mouth/chin too close to crop edge (likely cut off)
"""

import argparse
import sys

import cv2
import mediapipe as mp

# Landmarks (FaceMesh): https://github.com/google/mediapipe
# We'll use a few stable indices for mouth/chin checks.
MOUTH_INDICES = [13, 14, 78, 308]  # upper/lower lip center + mouth corners
CHIN_INDEX = 152
FOREHEAD_INDEX = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--min-mouth-margin", type=float, default=0.08, help="fraction of height")
    ap.add_argument("--min-chin-margin", type=float, default=0.05, help="fraction of height")
    ap.add_argument("--min-forehead-margin", type=float, default=0.05, help="fraction of height")
    args = ap.parse_args()

    bgr = cv2.imread(args.input)
    if bgr is None:
        print("ERROR: cannot read image", file=sys.stderr)
        return 1

    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    mp_face_mesh = mp.solutions.face_mesh
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as fm:
        res = fm.process(rgb)

    if not res.multi_face_landmarks:
        print("NO_FACE")
        return 2

    lm = res.multi_face_landmarks[0].landmark

    def xy(i):
        return lm[i].x, lm[i].y

    # collect key points
    pts = {"mouth": [xy(i) for i in MOUTH_INDICES], "chin": xy(CHIN_INDEX), "forehead": xy(FOREHEAD_INDEX)}

    # convert normalized y to pixel y
    mouth_ys = [p[1] * h for p in pts["mouth"]]
    chin_y = pts["chin"][1] * h
    forehead_y = pts["forehead"][1] * h

    # margins to edges
    mouth_bottom_margin = (h - max(mouth_ys)) / h
    chin_bottom_margin = (h - chin_y) / h
    forehead_top_margin = (forehead_y) / h

    ok = True
    reasons = []

    if mouth_bottom_margin < args.min_mouth_margin:
        ok = False
        reasons.append(f"mouth too close to bottom (margin={mouth_bottom_margin:.3f})")
    if chin_bottom_margin < args.min_chin_margin:
        ok = False
        reasons.append(f"chin too close to bottom (margin={chin_bottom_margin:.3f})")
    if forehead_top_margin < args.min_forehead_margin:
        ok = False
        reasons.append(f"forehead too close to top (margin={forehead_top_margin:.3f})")

    if ok:
        print("OK", {"mouth_bottom_margin": round(mouth_bottom_margin, 3), "chin_bottom_margin": round(chin_bottom_margin, 3), "forehead_top_margin": round(forehead_top_margin, 3)})
        return 0

    print("CUT_OFF", {"reasons": reasons, "mouth_bottom_margin": round(mouth_bottom_margin, 3), "chin_bottom_margin": round(chin_bottom_margin, 3), "forehead_top_margin": round(forehead_top_margin, 3)})
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
