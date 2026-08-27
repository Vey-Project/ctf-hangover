FROM kalilinux/kali-rolling

# System tools
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv \
    gdb gdbserver strace ltrace \
    radare2 \
    binwalk binutils file \
    nmap sqlmap gobuster feroxbuster dirb \
    nikto hydra john hashcat \
    curl wget netcat-traditional socat \
    steghide foremost exiftool \
    imagemagick tesseract-ocr \
    ffmpeg sox \
    git vim less jq bc \
    unzip p7zip-full \
    libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python CTF tools
RUN pip3 install --break-system-packages \
    pwntools ROPgadget \
    angr capstone unicorn keystone-engine \
    z3-solver gmpy2 pycryptodome sympy \
    volatility3 \
    pillow numpy scipy \
    flask requests beautifulsoup4 \
    r2pipe \
    scapy \
    impacket

# RsaCtfTool
RUN git clone --depth=1 https://github.com/RsaCtfTool/RsaCtfTool /opt/RsaCtfTool && \
    pip3 install --break-system-packages -r /opt/RsaCtfTool/requirements.txt && \
    ln -s /opt/RsaCtfTool/RsaCtfTool.py /usr/local/bin/rsactftool

# Stego tools
RUN pip3 install --break-system-packages stegoveritas && \
    stegoveritas_install_deps || true

# Wordlists
RUN mkdir -p /usr/share/wordlists && \
    wget -q https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10k-most-common.txt \
    -O /usr/share/wordlists/common.txt || true

# Non-root user
RUN useradd -m -s /bin/bash ctf
USER ctf
WORKDIR /home/ctf

CMD ["sleep", "3600"]
