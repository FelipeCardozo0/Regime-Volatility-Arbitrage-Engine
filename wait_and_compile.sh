#!/bin/bash
# Wait for LaTeX to be installed, then compile

echo "Waiting for LaTeX installation..."
echo "Please complete the BasicTeX installer that just opened."
echo ""

# Update PATH
eval "$(/usr/libexec/path_helper)" 2>/dev/null

# Wait for pdflatex to become available (max 5 minutes)
for i in {1..60}; do
    if command -v pdflatex &> /dev/null; then
        echo "✓ LaTeX found! Compiling PDF..."
        break
    fi
    if [ $i -eq 1 ]; then
        echo "Waiting for pdflatex to be available..."
    fi
    sleep 5
done

if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex still not found after waiting."
    echo "Please ensure BasicTeX installation completed, then run:"
    echo "  eval \"\$(/usr/libexec/path_helper)\""
    echo "  pdflatex main.tex"
    echo "  pdflatex main.tex"
    exit 1
fi

# Install required packages
echo "Installing required LaTeX packages..."
sudo tlmgr update --self 2>/dev/null
sudo tlmgr install ieeetran 2>/dev/null

# Compile
echo ""
echo "Compiling main.tex (first pass)..."
pdflatex -interaction=nonstopmode main.tex

echo ""
echo "Compiling main.tex (second pass)..."
pdflatex -interaction=nonstopmode main.tex

if [ -f main.pdf ]; then
    echo ""
    echo "✓ SUCCESS! PDF created: main.pdf"
    ls -lh main.pdf
else
    echo ""
    echo "✗ Error: PDF was not created. Check main.log for errors."
fi

