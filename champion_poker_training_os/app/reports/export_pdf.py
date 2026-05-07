def export_pdf_stub(html: str, path: str) -> dict:
    return {"path": path, "bytes": len(html.encode("utf-8")), "status": "HTML/PDF adapter placeholder"}

