import html
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which("google-chrome") or shutil.which("chromium")


def render_index_for_browser(check_mode):
    layout = (ROOT / "templates" / "layout.html.tera").read_text()
    index = (ROOT / "templates" / "index.html.tera").read_text()
    page = re.search(
        r"{% block page %}(.*){% endblock %}", index, re.DOTALL
    ).group(1)
    rendered = re.sub(
        r"{% block page %}.*?{% endblock %}",
        page,
        layout,
        count=1,
        flags=re.DOTALL,
    )
    rendered = rendered.replace(
        "</head>",
        "<style>.container{width:100%;padding:0 15px;margin:0 auto;}</style>"
        "</head>",
    )
    check_script = f"""
      <script>
        document.addEventListener('DOMContentLoaded', function() {{
          requestAnimationFrame(function() {{
            var rows = Array.from(document.querySelectorAll('.at-row'));
            var failures = [];
            if (rows.length !== 12) failures.push('expected 12 rows, got ' + rows.length);
            rows.forEach(function(row, index) {{
              var label = row.querySelector('.role-name');
              var value = row.querySelector('.at-value');
              if (!label || !value) {{
                failures.push('row ' + index + ' lacks structured fields');
                return;
              }}
              var rowBox = row.getBoundingClientRect();
              var labelBox = label.getBoundingClientRect();
              var valueBox = value.getBoundingClientRect();
              if ('{check_mode}' === 'mobile') {{
                if (valueBox.top < labelBox.bottom - 1) failures.push('row ' + index + ' is not stacked');
                if (row.scrollWidth > row.clientWidth || valueBox.right > rowBox.right + 1) failures.push('row ' + index + ' overflows');
              }} else {{
                if (valueBox.top >= labelBox.bottom) failures.push('row ' + index + ' lost desktop alignment');
              }}
            }});
            var result = document.createElement('pre');
            result.id = 'layout-test-result';
            result.textContent = failures.length ? 'FAIL: ' + failures.join('; ') : 'PASS';
            document.body.appendChild(result);
          }});
        }});
      </script>
    """
    return rendered.replace("</body>", check_script + "</body>")


@unittest.skipUnless(CHROME, "headless Chrome is required for layout tests")
class ResponsiveAtRowTests(unittest.TestCase):
    def assert_layout(self, mode, width, height):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            page_path = temp_path / "index.html"
            page_path.write_text(render_index_for_browser(mode))
            result = subprocess.run(
                [
                    CHROME,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    f"--user-data-dir={temp_path / 'profile'}",
                    "--virtual-time-budget=1000",
                    f"--window-size={width},{height}",
                    "--dump-dom",
                    page_path.as_uri(),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        match = re.search(
            r'<pre id="layout-test-result">(.*?)</pre>',
            result.stdout,
            re.DOTALL,
        )
        self.assertIsNotNone(match, result.stderr)
        self.assertEqual(html.unescape(match.group(1)), "PASS")

    def test_at_rows_stack_without_overflow_on_a_phone(self):
        self.assert_layout("mobile", 390, 844)

    def test_at_rows_remain_aligned_on_desktop(self):
        self.assert_layout("desktop", 1280, 900)


if __name__ == "__main__":
    unittest.main()
