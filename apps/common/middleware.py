from django.conf import settings


class SecurityHeaderMiddleware:
    """
    Middleware to inject essential security headers as recommended by django-security.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content-Security-Policy (CSP)
        csp = getattr(settings, "SECURE_CONTENT_SECURITY_POLICY", None)
        if csp:
            csp_parts = []
            for directive, sources in csp.items():
                if sources:
                    csp_parts.append(f"{directive} {' '.join(sources)}")
            response["Content-Security-Policy"] = "; ".join(csp_parts)

        # X-Content-Type-Options
        if getattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF", False):
            response["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options is usually handled by XFrameOptionsMiddleware
        # but we ensure it's explicitly set if configured
        x_frame_options = getattr(settings, "X_FRAME_OPTIONS", None)
        if x_frame_options:
            response["X-Frame-Options"] = x_frame_options

        # X-XSS-Protection
        if getattr(settings, "SECURE_BROWSER_XSS_FILTER", False):
            response["X-XSS-Protection"] = "1; mode=block"

        return response
