#!/usr/bin/env python3

"""Convert a BasicAnalysis printable HTML report to PDF."""

from __future__ import print_function

import argparse
import os
import shutil
import subprocess
import sys


CHROMIUM_CANDIDATES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)


def find_chromium():
    """Return the first available Chromium-compatible browser."""

    for executable in CHROMIUM_CANDIDATES:
        browser_path = shutil.which(executable)

        if browser_path:
            return browser_path

    return None


def html_to_pdf(input_html, output_pdf):
    """Convert a local HTML file to PDF using headless Chromium."""

    input_html = os.path.abspath(input_html)
    output_pdf = os.path.abspath(output_pdf)

    if not os.path.isfile(input_html):
        raise FileNotFoundError(
            "Input HTML file does not exist: {}".format(
                input_html
            )
        )

    browser_path = find_chromium()

    if browser_path is None:
        raise RuntimeError(
            "No Chromium-compatible browser was found. "
            "Install chromium or google-chrome."
        )

    output_dir = os.path.dirname(output_pdf)

    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    input_url = "file://{}".format(input_html)

    command = [
        browser_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--print-to-pdf={}".format(output_pdf),
        "--print-to-pdf-no-header",
        input_url,
    ]

    print(
        "==> Converting HTML report to PDF"
    )

    print(
        "==> Browser: {}".format(browser_path)
    )

    print(
        "==> Input HTML: {}".format(input_html)
    )

    print(
        "==> Output PDF: {}".format(output_pdf)
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "PDF generation failed.\n"
            "Command: {}\n"
            "stdout:\n{}\n"
            "stderr:\n{}".format(
                " ".join(command),
                result.stdout,
                result.stderr,
            )
        )

    if not os.path.isfile(output_pdf):
        raise RuntimeError(
            "Chromium completed but the PDF file was not created: "
            "{}".format(output_pdf)
        )

    print(
        "PDF report written to {}".format(output_pdf)
    )

    return output_pdf


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Convert a BasicAnalysis printable HTML report "
            "to PDF."
        )
    )

    parser.add_argument(
        "input_html",
        help="Input printable HTML report.",
    )

    parser.add_argument(
        "output_pdf",
        nargs="?",
        default=None,
        help=(
            "Output PDF file. If omitted, the input filename "
            "is reused with a .pdf extension."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    output_pdf = args.output_pdf

    if output_pdf is None:
        output_pdf = os.path.splitext(
            args.input_html
        )[0] + ".pdf"

    try:
        html_to_pdf(
            args.input_html,
            output_pdf,
        )

    except Exception as error:
        print(
            "==ERROR== {}".format(error),
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())