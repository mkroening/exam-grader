FROM python:3-bookworm

RUN pip install mypy black pytest pytest-cov

RUN apt-get update && apt-get install -y \
    cmake \
    gir1.2-gtk-3.0 \
    gir1.2-poppler-0.18 \
    ghostscript \
    libgirepository1.0-dev \
    libpoppler-cpp-dev \
    libpoppler-dev \
    python3-pip \
    python3-pythonmagick \
    python3-zbar

ARG ci_project_dir
WORKDIR $ci_project_dir
COPY pyproject.toml .

RUN pip install .

# Workaround for ghostscript-vulnerability policy
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read | write" pattern="PDF" \/>/'  /etc/ImageMagick-*/policy.xml