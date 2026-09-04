FROM kalilinux/kali-rolling

# System tools — includes extras for Cyber Academy CTF (WordPress, stego crack, pcap)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv \
    gdb gdbserver strace ltrace \
    radare2 \
    binwalk binutils file \
    nmap sqlmap gobuster feroxbuster dirb \
    nikto hydra john hashcat \
    curl wget netcat-traditional socat \
    smbclient \
    mariadb-client default-mysql-client \
    ftp \
    steghide foremost exiftool \
    imagemagick tesseract-ocr \
    ffmpeg sox \
    tshark \
    wpscan \
    git vim less jq bc \
    unzip p7zip-full \
    libssl-dev libffi-dev ruby ruby-dev \
    libimage-exiftool-perl \
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

# Stego crack tools (zsteg for PNG LSB, stegoveritas)
RUN gem install zsteg --no-document && \
    pip3 install --break-system-packages stegoveritas && \
    stegoveritas_install_deps || true

# stegseek — fast steghide passphrase cracker (uses prebuilt binary)
RUN STEGSEEK_VERSION="1.6" && \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
        libmbedtls-dev libmbedcrypto7 libmbedtls14 || true && \
    cd /tmp && \
    wget -q "https://github.com/RickdeJager/stegseek/releases/download/v${STEGSEEK_VERSION}/stegseek-backup_${STEGSEEK_VERSION}-1.deb" -O stegseek.deb && \
    apt-get install -y /tmp/stegseek.deb && \
    rm -f /tmp/stegseek.deb && \
    rm -rf /var/lib/apt/lists/* || echo "stegseek install failed (non-fatal, fallback to stegcracker/john)"

# RsaCtfTool
RUN git clone --depth=1 https://github.com/RsaCtfTool/RsaCtfTool /opt/RsaCtfTool && \
    pip3 install --break-system-packages -r /opt/RsaCtfTool/requirements.txt && \
    ln -s /opt/RsaCtfTool/RsaCtfTool.py /usr/local/bin/rsactftool

# Wordlists — full rockyou + SecLists 10k
RUN mkdir -p /usr/share/wordlists && \
    wget -q https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10k-most-common.txt \
    -O /usr/share/wordlists/common.txt || true && \
    wget -q https://raw.githubusercontent.com/brannondorsey/naive-hashcat/master/rockyou.txt \
    -O /usr/share/wordlists/rockyou.txt || echo "rockyou download failed (skip)"

# Wazuh API helper for SOC labs — pre-install Elasticsearch query tooling
RUN pip3 install --break-system-packages elasticsearch requests

# Non-root user
RUN useradd -m -s /bin/bash ctf
USER ctf
WORKDIR /home/ctf

CMD ["sleep", "3600"]
