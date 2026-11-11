# Gaming and cricket image direction

The owner initially requested a direct AI Images workspace, persistent guidance
for Gaming and Cricket, and demonstrations from the actual local generator.
The later instruction in the “youtube thumbnail” chat consolidates that interface
into **Thumbnail**: YouTube thumbnail, Instagram cover, Social post, Poster and
General image. Do not restore a separate AI Images tool or chat selection.
Existing image projects, style knowledge and compatibility backends are retained.

`hinglish_aigen/channel_knowledge.json` supplies reusable genre-specific direction
to both configured local planners for the unified image-concept schema, and to
the legacy image planner. It covers gaming genre/world consistency, readable
action, grip/geometry, cricket bats/balls/stumps/creases, phases of play, scene
composition and factual versus invented imagery. Full creator guidance remains
in the request. This is retrieval and prompt direction, not weight training.

Real unified Thumbnail jobs save `image-channel-guidance.json` alongside the
creator-context file under their job folder, recording original idea, design,
actual planner and the knowledge version/hash. Legacy direct projects additionally
save `image-direction.json` and retain editable prompts/downloads/rebuilds.

Keep generated-result quality claims tied to inspected images. Automated checks
and isolated tests are not proof of a live workflow or an improvement benchmark.
