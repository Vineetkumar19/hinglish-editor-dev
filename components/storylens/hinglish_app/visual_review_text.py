"""Raw manual-bank instructions, separate from the retained legacy rebuild."""


def message(summary,*,raw=False):
    count=summary['options'];subjects=summary['subjects']
    if not raw:
        return (f'{count} visual choices are ready for {subjects} spoken subjects. '
            'Open View Result, choose the visuals you like, then Save & rebuild before sending your selected layers to an editor. '
            'Missing verified choices stay empty.')
    lead=(f'{count} raw source-image choices are available for {subjects} spoken subjects. ' if count else
          f'No verified source images are available for these {subjects} spoken subjects. ')
    return lead+('In your editor’s Storylens panel, open Saved visual review. Choose No visual for an empty subject, '
        'or import your chosen source images into the project bin and place them yourself. Nothing was placed automatically.')
