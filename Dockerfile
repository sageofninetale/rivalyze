# ─────────────────────────────────────────────────────────────
# BASE IMAGE
# ─────────────────────────────────────────────────────────────
# FROM tells Docker: "start from this pre-built image."
# python:3.11-slim is an official Python image maintained by Docker.
# "3.11" pins the Python version so your code behaves the same everywhere.
# "slim" means it ships only the essentials — ~50 MB instead of ~350 MB.
# Without FROM, Docker has nothing to build on top of.
FROM python:3.11-slim

# ─────────────────────────────────────────────────────────────
# WORKING DIRECTORY
# ─────────────────────────────────────────────────────────────
# WORKDIR sets the "current folder" inside the container for every
# instruction that follows (COPY, RUN, CMD, etc.).
# If the directory doesn't exist Docker creates it automatically.
# Using /app is a convention — it keeps your code separate from
# system files that live in / or /usr.
WORKDIR /app

# ─────────────────────────────────────────────────────────────
# COPY REQUIREMENTS FIRST (cache optimisation)
# ─────────────────────────────────────────────────────────────
# COPY <source-on-your-machine> <destination-inside-container>
# We copy requirements.txt before the rest of the code because
# Docker caches each layer. If requirements.txt hasn't changed,
# Docker skips the expensive pip install step on the next build.
# This is one of the most important Dockerfile tricks to know.
COPY requirements.txt .

# ─────────────────────────────────────────────────────────────
# INSTALL DEPENDENCIES
# ─────────────────────────────────────────────────────────────
# RUN executes a shell command while building the image.
# pip install -r requirements.txt reads the file and installs
# every package listed in it.
# --no-cache-dir tells pip NOT to save a download cache inside
# the image — keeps the final image smaller.
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────
# COPY THE REST OF YOUR CODE
# ─────────────────────────────────────────────────────────────
# The first "." means "everything in the folder on your machine
# where you run docker build" (called the build context).
# The second "." means "put it in the current WORKDIR (/app)".
# We do this AFTER pip install so changing hello.py doesn't
# bust the pip cache layer.
COPY . .

# ─────────────────────────────────────────────────────────────
# DEFAULT COMMAND
# ─────────────────────────────────────────────────────────────
# CMD tells Docker what to run when someone does "docker run <image>".
# It is NOT executed during the build — only at runtime.
# The array form ["python", "hello.py"] is preferred over a plain
# string because it avoids a shell wrapper, which means signals
# (like Ctrl-C) reach Python directly instead of getting lost.
CMD ["python", "hello.py"]
