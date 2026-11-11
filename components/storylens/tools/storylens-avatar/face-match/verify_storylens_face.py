"""Verify the installed StoryLens avatar in an isolated loopback-only Edge session."""
import argparse
import base64
import hashlib
import io
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlsplit
import wave

from playwright.sync_api import sync_playwright


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGIN = "http://127.0.0.1:8765"
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
RENDERER = re.compile(r"/cortana-3d(?:-[\w-]+)?\.js$")
GREETING = ROOT / "cache/app/voice-help/help-d0d3d03e3a3b95c83e8bb370df833d6896b3d2c90a747c4747cfd667414de674.wav"
SAMPLE = """
    if (model) {
      const proof = window.faceReview ||= {frames:0,jaw:0,blinkL:0,blinkR:0,peakClosure:0,peakSpeech:0};
      const names = ['jaw', 'orbicularis03L', 'orbicularis03R'];
      const joints = names.map(name => model.getObjectByName(name));
      if (joints.every(Boolean)) {
        proof.joints = names;
        const base = window.faceReviewRest || [];
        proof.frames++;
        proof.peakClosure = Math.max(proof.peakClosure,closure);
        proof.peakSpeech = Math.max(proof.peakSpeech,energy);
        if (energy > .03 && base[0]) proof.jaw = Math.max(proof.jaw,joints[0].quaternion.angleTo(base[0]));
        if (closure > .1 && base[1]) {
          proof.blinkL = Math.max(proof.blinkL,joints[1].quaternion.angleTo(base[1]));
          proof.blinkR = Math.max(proof.blinkR,joints[2].quaternion.angleTo(base[2]));
        }
      }
    }
"""
MIC = """navigator.mediaDevices.getUserMedia = async () => {
    const context = new AudioContext();
    await context.resume();
    return context.createMediaStreamDestination().stream;
};"""


def greeting_fixture():
    """Use real cached StoryLens speech with a lead-in for model initialization."""
    with wave.open(str(GREETING), "rb") as audio:
        params = audio.getparams()
        speech = audio.readframes(params.nframes)
    silence = bytes(params.framerate * params.nchannels * params.sampwidth)
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setparams(params)
        output.writeframes(silence + speech + speech)
    return {"ready": True, "greeting_audio": base64.b64encode(stream.getvalue()).decode("ascii")}


def staged_paths(values):
    assets = {}
    for pair in values:
        if "=" not in pair:
            raise ValueError("Use --asset /web-path=local-file")
        path, file = pair.split("=", 1)
        if not path.startswith("/") or not Path(file).is_file():
            raise ValueError(f"Invalid staged asset {pair}")
        assets[path] = Path(file)
    return assets


def check(args):
    stage_assets = staged_paths(args.asset)
    greeting = greeting_fixture()
    errors = []
    failed_assets = []
    receipt = {"voice": "cached StoryLens greeting", "avatars": {}, "voice_warm_calls": 0}
    args.output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=EDGE,
            headless=True,
            args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                  "--disable-background-networking", "--disable-sync", "--no-first-run", "--mute-audio"],
        )
        context = browser.new_context(viewport={"width": 1180, "height": 930}, reduced_motion="no-preference")
        context.add_init_script(MIC)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text)
                if "shader error" in message.text.lower() else None)

        def route_app(route):
            url = urlsplit(route.request.url)
            if f"{url.scheme}://{url.netloc}" != ORIGIN:
                route.abort()
                return
            path = url.path
            if path == "/api/support-call/local-warm":
                receipt["voice_warm_calls"] += 1
                if args.live_voice:
                    try:
                        live = route.fetch(timeout=15000)
                        receipt["live_voice_http"] = live.status
                        if live.ok and live.json().get("greeting_audio"):
                            receipt["voice"] = "live StoryLens greeting"
                            route.fulfill(response=live)
                            return
                    except Exception as error:
                        receipt["live_voice_error"] = type(error).__name__
                route.fulfill(status=200, json=greeting)
                return
            if path == "/api/support-call/local-end" and not args.live_voice:
                route.fulfill(status=200, json={"ended": True})
                return
            if RENDERER.fullmatch(path) and "vendor" not in path:
                source = stage_assets[path].read_text(encoding="utf-8") if path in stage_assets else route.fetch().text()
                needle = "    renderer.render(scene,camera);"
                if source.count(needle) != 1:
                    failed_assets.append(f"Cannot attach motion probe to {path}")
                    route.abort()
                    return
                blink = "const blinkPhase=(t+1.5)%9.7;"
                if source.count(blink) != 1:
                    failed_assets.append(f"Cannot attach blink stimulus to {path}")
                    route.abort()
                    return
                source = source.replace(blink, "const blinkPhase=window.faceReviewBlink ? .43 : (t+1.5)%9.7;")
                rest = "jaw=motionJoint(model.getObjectByName('jaw'));"
                if source.count(rest) != 1:
                    failed_assets.append(f"Cannot record the resting face rig in {path}")
                    route.abort()
                    return
                source = source.replace(rest, rest + """
                    window.faceReviewRest = ['jaw','orbicularis03L','orbicularis03R']
                        .map(name => model.getObjectByName(name)?.quaternion.clone());
                """)
                route.fulfill(content_type="text/javascript", body=source.replace(needle, SAMPLE + needle))
                receipt["renderer"] = path
                return
            if path.endswith(".glb") and path.startswith("/cortana"):
                response = None if path in stage_assets else route.fetch()
                if response is not None and not response.ok:
                    failed_assets.append(f"{path} returned {response.status}")
                    route.fulfill(response=response)
                    return
                body = stage_assets[path].read_bytes() if response is None else response.body()
                receipt["avatars"][path] = hashlib.sha256(body).hexdigest()
                route.fulfill(status=200, content_type="model/gltf-binary", body=body)
                return
            if path in stage_assets:
                route.fulfill(path=stage_assets[path], content_type=mimetypes.guess_type(path)[0])
                return
            route.continue_()

        context.route("**/*", route_app)
        try:
            page.goto(ORIGIN, wait_until="domcontentloaded", timeout=20000)
            page.locator("[data-support-call]").click(timeout=6000)
            page.wait_for_selector("[data-call-stage][data-model=ready] canvas", timeout=25000)
            page.locator("[data-call-expand]").click(timeout=6000)
            page.locator("[data-call-closeup]").click(timeout=6000)
            page.wait_for_function("window.faceReview?.jaw > .035", timeout=16000)
            natural = page.evaluate("window.faceReview.blinkL > .12 && window.faceReview.blinkR > .12")
            if not natural:
                page.evaluate("window.faceReviewBlink = true")
                page.wait_for_function("window.faceReview.blinkL > .12 && window.faceReview.blinkR > .12", timeout=5000)
                page.evaluate("window.faceReviewBlink = false")
            receipt["blink_stimulus"] = "natural blink" if natural else "controlled clock stimulus"
            receipt["animation"] = page.evaluate("window.faceReview")
            page.wait_for_function("document.querySelector('dialog.support-call').dataset.phase==='ready'", timeout=15000)
            stage = page.locator("[data-call-stage]")
            stage.screenshot(path=str(args.output / "StoryLens front close-up.png"), timeout=15000)
            page.screenshot(path=str(args.output / "StoryLens face detail.png"),
                            clip={"x": 355, "y": 144, "width": 470, "height": 435}, timeout=15000)
            for key, name in (("ArrowRight", "right"), ("ArrowLeft", "left")):
                stage.press("Home")
                stage.press(key)
                stage.press(key)
                page.wait_for_timeout(1200)
                stage.screenshot(path=str(args.output / f"StoryLens {name} three-quarter.png"), timeout=15000)
            assert receipt["avatars"], "No Cortana 3D mesh was requested"
            assert not errors and not failed_assets, errors + failed_assets
            receipt["status"] = "passed"
        finally:
            receipt["animation"] = page.evaluate("window.faceReview")
            receipt["final_phase"] = page.locator("#storylens-call-panel").get_attribute("data-phase")
            receipt["errors"] = errors + failed_assets
            if page.locator("[data-call-end]").is_visible():
                page.locator("[data-call-end]").dispatch_event("click")
            context.close()
            browser.close()
            (args.output / "face-review.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "browser-review")
    parser.add_argument("--asset", action="append", default=[], metavar="/URL=FILE",
                        help="Serve a staged asset only inside the test browser")
    parser.add_argument("--live-voice", action="store_true", help="Try live voice startup before the cached greeting")
    check(parser.parse_args())

