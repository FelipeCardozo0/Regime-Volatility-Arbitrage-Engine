#!/bin/bash
# Compilation script for main.tex

# Check if pdflatex is available
if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex not found."
    echo ""
    echo "To install LaTeX on macOS, run:"
    echo "  brew install --cask basictex"
    echo ""
    echo "After installation, update your PATH:"
    echo "  eval \"\$(/usr/libexec/path_helper)\""
    echo ""
    echo "Then install required packages:"
    echo "  sudo tlmgr update --self"
    echo "  sudo tlmgr install ieeetran"
    exit 1
fi

# Compile the document (run twice for cross-references)
echo "Compiling main.tex (first pass)..."
pdflatex -interaction=nonstopmode main.tex

echo ""
echo "Compiling main.tex (second pass for cross-references)..."
pdflatex -interaction=nonstopmode main.tex

# Check if PDF was created
if [ -f main.pdf ]; then
    echo ""
    echo "✓ Success! PDF created: main.pdf"
else
    echo ""
    echo "✗ Error: PDF was not created. Check the log file for errors."
    exit 1
fi

