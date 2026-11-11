"""Generate editable After Effects time maps without launching or replacing projects."""
import json


def write_aftereffects(folder, variant):
    data = {
        "source": variant["moment"]["source"], "folder": str(folder),
        "width": variant["width"], "height": variant["height"],
        "fps": variant["fps"], "frames": variant["frames"],
        "ticks": variant["time_map"]["source_ticks"],
        "reference": variant["sha256"],
    }
    script = r'''
(function(s) {
    function record(name, value) {
        var f = new File(s.folder + "/" + name);
        if (!f.open("w")) throw new Error("Cannot write " + f.fsName);
        try { f.write(value); } finally { f.close(); }
    }
    try {
        if (app.project && (app.project.file || app.project.numItems || app.project.renderQueue.numItems))
            throw new Error("Save your current work, then open an empty project before running this script.");
        var target = new File(s.folder + "/Editable Pixel Motion.aep");
        if (target.exists) throw new Error("The native project already exists. Open it to resume.");
        var project = app.project || app.newProject();
        var footage = project.importFile(new ImportOptions(new File(s.source)));
        var comp = project.items.addComp("Selective Slow Motion", s.width, s.height, 1, s.frames / s.fps, s.fps);
        comp.frameBlending = true;
        var layer = comp.layers.add(footage);
        layer.audioEnabled = false;
        layer.timeRemapEnabled = true;
        layer.frameBlendingType = FrameBlendingType.PIXEL_MOTION;
        layer.inPoint = 0;
        layer.outPoint = comp.duration;
        var remap = layer.property("ADBE Time Remapping");
        for (var i = 0; i < s.frames; i++) {
            remap.setValueAtTime(i / s.fps, s.ticks[i] / 1000000);
        }
        for (var k = remap.numKeys; k >= 1; k--)
            if (remap.keyTime(k) > (s.frames - 1) / s.fps + 0.000001) remap.removeKey(k);
        for (var q = 1; q <= remap.numKeys; q++)
            remap.setInterpolationTypeAtKey(q, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR);
        for (var j = 0; j < s.frames; j++)
            if (Math.abs(remap.valueAtTime(j / s.fps, false) - s.ticks[j] / 1000000) > 0.000002)
                throw new Error("Native time map differs at output frame " + j);
        if (!comp.frameBlending || layer.frameBlendingType !== FrameBlendingType.PIXEL_MOTION)
            throw new Error("Pixel Motion settings did not persist.");
        var item = project.renderQueue.items.add(comp);
        item.setSetting("Quality", "Best");
        item.setSetting("Resolution", "Full");
        item.setSetting("Frame Blending", "On for Checked Layers");
        var templates = item.outputModule(1).templates;
        var selected = "";
        for (var n = 0; n < templates.length; n++)
            if (templates[n].indexOf("H.264") === 0) { selected = templates[n]; break; }
        if (!selected) throw new Error("No installed H.264 output module template. Choose one manually.");
        item.outputModule(1).applyTemplate(selected);
        item.outputModule(1).file = new File(s.folder + "/Adobe Pixel Motion.mp4");
        project.save(target);
        record("Native settings.txt", "Reference SHA256: " + s.reference + "\nAfter Effects: " + app.version +
               "\nEditable source time keys: " + remap.numKeys + "\nPixel Motion: true\nComposition blending: true" +
               "\nFrames: " + s.frames + "\nFPS: " + s.fps + "\nAudio: muted; original separate audio is preserved on export when selected\n");
        comp.openInViewer();
    } catch (e) { record("Native error.txt", String(e)); alert(String(e)); }
})(settings);
'''
    (folder / "Build Editable Pixel Motion.jsx").write_text(
        "var settings = " + json.dumps(data) + ";\n" + script, "utf-8")
