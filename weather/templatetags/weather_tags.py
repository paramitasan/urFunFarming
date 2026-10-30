from django import template

from weather.services import forecast_for_user

register = template.Library()


def _forecast(context):
    # Worked out once per request, however many times a page asks
    request = context.get('request')
    if request is None:
        return forecast_for_user(None)
    if not hasattr(request, '_weather_forecast'):
        request._weather_forecast = forecast_for_user(request.user)
    return request._weather_forecast


@register.simple_tag(takes_context=True)
def user_forecast(context):
    """{% user_forecast as weather %} gives the normalized forecast for the current user."""
    return _forecast(context)


@register.inclusion_tag('weather/_line.html', takes_context=True)
def weather_line(context):
    """{% weather_line %} shows one line of current weather with the BMKG source."""
    return {'weather': _forecast(context)}
