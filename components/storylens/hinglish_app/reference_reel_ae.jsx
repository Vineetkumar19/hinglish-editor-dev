(function () {
    var plan = __REFERENCE_REEL_PLAN__;
    var fps = plan.fps_number;
    var duration = plan.frame_count / fps;
    var tag = "Reference Reel " + plan.analysis.substring(0, 8);
    var folder, comp, items = {}, generatedSolids = [];

    function loadMedia(path, label) {
        if (items[path]) return items[path];
        var file = new File(path);
        if (!file.exists) throw new Error("Media missing: " + file.fsName);
        var item = app.project.importFile(new ImportOptions(file));
        item.parentFolder = folder;
        item.name = label;
        items[path] = item;
        return item;
    }

    function marker(time, title, note) {
        var value = new MarkerValue(title);
        value.comment = title + " | " + note;
        comp.markerProperty.setValueAtTime(time, value);
    }

    function makeLayer(shot, index) {
        var start = shot.start / fps;
        if (!shot.source) {
            var gap = comp.layers.addSolid([0.25, 0.09, 0.09], "Unmapped shot " + (index + 1),
                comp.width, comp.height, 1, duration);
            generatedSolids.push(gap.source);
            gap.source.parentFolder = folder;
            gap.inPoint = start;
            gap.outPoint = shot.end / fps;
            return;
        }
        var item = loadMedia(shot.source.path, shot.source.name);
        var next = plan.shots[index + 1];
        var dissolveTail = next && next.transition === "dissolve" ? next.transition_frames / fps : 0;
        var layer = comp.layers.add(item);
        layer.name = "Shot " + (index + 1) + " | " + shot.source.name;
        layer.audioEnabled = false;
        layer.comment = "Reference frames " + shot.start + " to " + shot.end +
            " | source SHA-256 " + shot.source.sha256 + " | " + shot.evidence;
        if (!layer.canSetTimeRemapEnabled) throw new Error("Cannot retime " + item.name);
        layer.timeRemapEnabled = true;
        if (shot.interpolation === "optical") {
            comp.frameBlending = true;
            layer.frameBlendingType = FrameBlendingType.PIXEL_MOTION;
        }
        layer.startTime = start;
        layer.inPoint = start;
        layer.outPoint = shot.end / fps + dissolveTail;
        var remap = layer.property("ADBE Time Remapping");
        var defaults = [];
        for (var j = 1; j <= remap.numKeys; j++) defaults.push(remap.keyTime(j));
        var time = [], value = [];
        for (var frame = 0; frame < shot.time_map.length; frame++) {
            time.push(start + shot.time_map[frame][0] / fps);
            value.push(shot.time_map[frame][1]);
        }
        if (dissolveTail > 0) {
            time.push(shot.end / fps + dissolveTail);
            value.push(shot.source_out + dissolveTail * shot.speed_out);
        }
        remap.setValuesAtTimes(time, value);
        for (var j = defaults.length - 1; j >= 0; j--) {
            var retained = false;
            for (var k = 0; k < time.length; k++) {
                if (Math.abs(time[k] - defaults[j]) < 0.00001) { retained = true; break; }
            }
            if (!retained) remap.removeKey(remap.nearestKeyIndex(defaults[j]));
        }
        for (var k = 1; k <= remap.numKeys; k++)
            remap.setInterpolationTypeAtKey(k, KeyframeInterpolationType.LINEAR);

        var fit = Math.min(comp.width / item.width, comp.height / item.height);
        var scale = layer.property("ADBE Transform Group").property("ADBE Scale");
        var from = fit * shot.zoom_in, to = fit * shot.zoom_out;
        if (shot.transition === "whip-left" || shot.transition === "whip-right") {
            var settle = start + shot.transition_frames / fps;
            var settleScale = from + (to - from) * shot.transition_frames / (shot.end - shot.start);
            var position = layer.property("ADBE Transform Group").property("ADBE Position");
            var center = [comp.width / 2, comp.height / 2];
            var offset = comp.width * (shot.transition === "whip-left" ? -0.08 : 0.08);
            position.setValuesAtTimes([start, settle], [[center[0] + offset, center[1]], center]);
            scale.setValuesAtTimes([start, settle, shot.end / fps],
                [[from * 1.16, from * 1.16], [settleScale, settleScale], [to, to]]);
            layer.motionBlur = true;
            comp.motionBlur = true;
        } else if (from === to) scale.setValue([from, from]);
        else scale.setValuesAtTimes([start, shot.end / fps], [[from, from], [to, to]]);
        if (shot.transition === "dissolve") {
            var opacity = layer.property("ADBE Transform Group").property("ADBE Opacity");
            opacity.setValuesAtTimes([start, start + shot.transition_frames / fps], [0, 100]);
        }

        if (shot.exposure !== 0) {
            var effects = layer.property("ADBE Effect Parade");
            if (!effects.canAddProperty("ADBE Exposure2"))
                throw new Error("This After Effects build does not offer the native Exposure effect.");
            var exposure = effects.addProperty("ADBE Exposure2");
            var stops = exposure.property("Exposure");
            if (!stops || stops.propertyValueType !== PropertyValueType.OneD)
                throw new Error("The Exposure control could not be located.");
            stops.setValue(shot.exposure);
        }
        if (shot.contrast_adjustment) {
            var effects = layer.property("ADBE Effect Parade");
            if (!effects.canAddProperty("ADBE Brightness & Contrast 2"))
                throw new Error("This After Effects build does not offer Brightness & Contrast.");
            var correction = effects.addProperty("ADBE Brightness & Contrast 2").property(2);
            if (!correction || correction.propertyValueType !== PropertyValueType.OneD)
                throw new Error("The native Contrast control could not be located.");
            correction.setValue(shot.contrast_adjustment);
        }
        if (shot.flash_frame !== null) {
            var flash = comp.layers.addSolid([1, 1, 1], "Flash | frame " + shot.flash_frame,
                comp.width, comp.height, 1, duration);
            generatedSolids.push(flash.source);
            flash.source.parentFolder = folder;
            flash.inPoint = shot.flash_frame / fps;
            flash.outPoint = (shot.flash_frame + 1) / fps;
            flash.property("ADBE Transform Group").property("ADBE Opacity").setValue(shot.flash_opacity);
        }
    }

    app.beginUndoGroup(tag);
    try {
        folder = app.project.items.addFolder(tag);
        comp = app.project.items.addComp(tag, plan.width, plan.height, 1, duration, fps);
        comp.parentFolder = folder;
        comp.comment = "Reference SHA-256 " + plan.reference.sha256 + "\n" + plan.unresolved.join("\n");
        var audio = plan.audio_tracks || (plan.audio_path ? [{path: plan.audio_path, name: "Reference soundtrack"}] : []);
        for (var a = 0; a < audio.length; a++) {
            var soundtrack = comp.layers.add(loadMedia(audio[a].path, audio[a].name));
            soundtrack.startTime = 0;
            soundtrack.outPoint = duration;
        }
        var markers = {}, i;
        for (i = 0; i < plan.shots.length; i++) {
            makeLayer(plan.shots[i], i);
            markers[plan.shots[i].start] = "Shot " + (i + 1);
        }
        for (i = 0; i < plan.onsets.length; i++) {
            var frame = plan.onsets[i].frame;
            markers[frame] = markers[frame] ? markers[frame] + " + audio onset" : "Audio onset";
        }
        for (var frameNumber in markers) {
            if (markers.hasOwnProperty(frameNumber))
                marker(Number(frameNumber) / fps, markers[frameNumber], "Reference frame " + frameNumber);
        }
        comp.openInViewer();
    } catch (error) {
        if (comp) comp.remove();
        for (var path in items) if (items.hasOwnProperty(path)) items[path].remove();
        for (var j = 0; j < generatedSolids.length; j++) generatedSolids[j].remove();
        if (folder) folder.remove();
        throw error;
    } finally {
        app.endUndoGroup();
    }
}());
