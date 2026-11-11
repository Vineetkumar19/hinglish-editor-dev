"""Owner-approved final choice budgets; legacy six-option requests remain readable."""

def choice_limit(requested=None, orientation=None, timeline=None, output_format=None):
    if orientation not in (None, 'vertical', 'horizontal'):
        raise ValueError('Choose Vertical or Horizontal.')
    if requested is not None and (type(requested) is not int or not 1 <= requested <= 6):
        raise ValueError('Choose one to five video options (YouTube allows up to two).')
    horizontal = orientation == 'horizontal'
    if orientation is None:
        horizontal = output_format == 'youtube_horizontal'
        if output_format is None and timeline:
            horizontal = timeline.get('width', 0) > timeline.get('height', 0)
    maximum = 2 if horizontal else 5
    return maximum if requested is None else min(requested, maximum)
