"""PDF Generator."""

from datetime import datetime
from typing import Any

from fpdf import FPDF

from open_webui.env import env
from open_webui.models.chats import ChatTitleMessagesForm


class PDFGenerator:
    """PDF Generator.

    The `PDFGenerator` class is designed to create PDF documents from chat messages.
    The process involves transforming markdown content into HTML and then into a PDF format

    Attributes:
    - `form_data`: An instance of `ChatTitleMessagesForm` containing title and messages.

    """

    def __init__(self, form_data: ChatTitleMessagesForm):  # noqa: D107
        self.html_body = None
        self.messages_html = None
        self.form_data = form_data

        self.css = (env.STATIC_DIR / "assets" / "pdf-style.css").read_text()

    def format_timestamp(self, timestamp: float) -> str:
        """Convert a UNIX timestamp to a formatted date string."""
        try:
            date_time = datetime.fromtimestamp(timestamp)
            return date_time.strftime("%Y-%m-%d, %H:%M:%S")
        except (ValueError, TypeError):
            # Log the error if necessary
            return ""

    def _build_html_message(self, message: dict[str, Any]) -> str:
        """Build HTML for a single message."""
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = message.get("timestamp")

        model = message.get("model") if role == "assistant" else ""

        date_str = self.format_timestamp(timestamp) if timestamp else ""

        # extends pymdownx extension to convert markdown to html.
        # - https://facelessuser.github.io/pymdown-extensions/usage_notes/
        # html_content = markdown(content, extensions=["pymdownx.extra"])

        html_message = f"""
            <div>
                <div>
                    <h4>
                        <strong>{role.title()}</strong>
                        <span style="font-size: 12px;">{model}</span>
                    </h4>
                    <div> {date_str} </div>
                </div>
                <br/>
                <br/>

                <div>
                    {content}
                </div>
            </div>
            <br/>
          """
        return html_message

    def _generate_html_body(self) -> str:
        """Generate the full HTML body for the PDF."""
        return f"""
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            </head>
            <body>
            <div>
                <div>
                    <h2>{self.form_data.title}</h2>
                    {self.messages_html}
                </div>
            </div>
            </body>
        </html>
        """

    def generate_chat_pdf(self) -> bytes:
        """Generate a PDF from chat messages."""
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("NotoSans", "", f"{env.FONTS_DIR}/NotoSans-Regular.ttf")
        pdf.add_font("NotoSans", "B", f"{env.FONTS_DIR}/NotoSans-Bold.ttf")
        pdf.add_font("NotoSans", "I", f"{env.FONTS_DIR}/NotoSans-Italic.ttf")
        pdf.add_font("NotoSansKR", "", f"{env.FONTS_DIR}/NotoSansKR-Regular.ttf")
        pdf.add_font("NotoSansJP", "", f"{env.FONTS_DIR}/NotoSansJP-Regular.ttf")
        pdf.add_font("NotoSansSC", "", f"{env.FONTS_DIR}/NotoSansSC-Regular.ttf")
        pdf.add_font("Twemoji", "", f"{env.FONTS_DIR}/Twemoji.ttf")

        pdf.set_font("NotoSans", size=12)
        pdf.set_fallback_fonts(["NotoSansKR", "NotoSansJP", "NotoSansSC", "Twemoji"])

        pdf.set_auto_page_break(auto=True, margin=15)

        # Build HTML messages
        messages_html_list: list[str] = [
            self._build_html_message(msg) for msg in self.form_data.messages
        ]
        self.messages_html = "<div>" + "".join(messages_html_list) + "</div>"

        # Generate full HTML body
        self.html_body = self._generate_html_body()

        pdf.write_html(self.html_body)

        # Save the pdf with name .pdf
        pdf_bytes = pdf.output()

        return bytes(pdf_bytes)
