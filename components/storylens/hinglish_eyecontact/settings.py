"""Eye Contact settings and the local install config written by the RTX setup script."""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json

CONFIG_NAME = 'config.eyecontact.local.json'   # machine-specific paths only (no keys); kept out of git
FEATURES = ('nvARGazeRedirection', 'nvARLandmarkDetection', 'nvARFaceBoxDetection')

# Where the script sits relative to the lens. NVIDIA fades the redirection out between the low and
# high gaze angle (degrees), so eyes that look far away are left alone instead of looking fake.
REACH = {
    'near': {},                                               # laptop / phone right under the camera
    'far': {'gaze_pitch_threshold_low': 25, 'gaze_pitch_threshold_high': 35,   # paper on the desk,
            'gaze_yaw_threshold_low': 25, 'gaze_yaw_threshold_high': 35},    # screen to the side
}
EYE_SIZE = range(2, 7)          # NVIDIA eyesize_sensitivity; 3 is the default
LOOK_AWAY = {'look_away_offset_max': 5, 'look_away_interval_min': 3, 'look_away_interval_range': 8}


@dataclass
class EyeSettings:
    reach: str = 'near'
    look_away: bool = True        # tiny natural glances so you never "stare"
    eye_size: int = 3
    quality: int = 17             # constant-quality level of the final encode (lower = better)
    backend: str = 'maxine'

    def gaze_flags(self):
        # NVIDIA's sample defaults to a side-by-side debug view with drawings: both must be off.
        flags = ['--offline_mode', '--split_screen_view=false', '--draw_visualization=false',
                 '--temporal', '--landmarks_126', '--use_cuda_graph',
                 f'--eyesize_sensitivity={self.eye_size}']
        flags += [f'--{k}={v}' for k, v in REACH[self.reach].items()]
        if self.look_away:
            flags.append('--enable_look_away')
            flags += [f'--{k}={v}' for k, v in LOOK_AWAY.items()]
        return flags

    def key(self):
        """Changes whenever the eyes would come out different (the encode quality does not count)."""
        data = {k: v for k, v in asdict(self).items() if k != 'quality'}
        return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]


def load_install(root):
    path = Path(root) / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}
