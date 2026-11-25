"""On-screen text via macOS Vision (built in, no extra service)."""
import cv2


def read_text(img):
    """img: BGR array. Returns [(text, confidence, (x, y, w, h) in image pixels)], top to bottom."""
    import Quartz
    import Vision
    from Foundation import NSData
    ok, buf = cv2.imencode(".png", img)
    data = NSData.dataWithBytes_length_(buf.tobytes(), len(buf))
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    h, w = img.shape[:2]
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    handler.performRequests_error_([req], None)
    out = []
    for o in req.results() or []:
        c = o.topCandidates_(1)[0]
        (bx, by), (bw, bh) = o.boundingBox().origin, o.boundingBox().size  # normalised, origin bottom-left
        out.append((c.string(), c.confidence(), (bx * w, (1 - by - bh) * h, bw * w, bh * h)))
    return sorted(out, key=lambda t: (t[2][1], t[2][0]))
