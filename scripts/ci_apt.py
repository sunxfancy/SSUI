"""Prepare Ubuntu APT on disposable GitHub runners without accepting stale indexes."""
import os
from pathlib import Path
import re
import subprocess


UBUNTU_URI = re.compile(
    r"https?://(?:(?:[\w-]+\.)?archive\.ubuntu\.com/ubuntu|"
    r"security\.ubuntu\.com/ubuntu|ports\.ubuntu\.com/ubuntu-ports)/?"
    r"(?=\s|$)|mirror\+file:/etc/apt/(?:apt-mirrors\.txt|mirrors/ubuntu(?:-security)?\.list)"
)
MIRRORS = {
    'amd64': ('https://mirror.math.princeton.edu/pub/ubuntu/',
              'https://archive.ubuntu.com/ubuntu/'),
    'arm64': ('https://mirrors.aliyun.com/ubuntu-ports/',
              'https://ports.ubuntu.com/ubuntu-ports/'),
}
APT_CONFIG = '''Acquire::Retries "1";
Acquire::http::Timeout "20";
Acquire::https::Timeout "20";
APT::Update::Error-Mode "any";
'''


def rewrite_sources(text, mirror):
    # Retain suites, components, architecture restrictions and Signed-By keys.
    return ''.join(line if line.lstrip().startswith('#') else UBUNTU_URI.sub(mirror, line)
                   for line in text.splitlines(keepends=True))


def prepare(apt_root, arch, run=subprocess.run):
    mirrors = MIRRORS[arch]
    paths = [apt_root / 'sources.list', *(apt_root / 'sources.list.d').glob('*.list'),
             *(apt_root / 'sources.list.d').glob('*.sources')]
    originals = {p: p.read_text() for p in paths if p.is_file()}
    if not any(UBUNTU_URI.search(text) for text in originals.values()):
        raise RuntimeError('No Ubuntu package source found; refusing to guess repository configuration')
    config = apt_root / 'apt.conf.d' / '80ssui-ci-network'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(APT_CONFIG)
    for mirror in mirrors:
        for path, text in originals.items():
            path.write_text(rewrite_sources(text, mirror))
        print(f'Updating signed Ubuntu indexes from {mirror}', flush=True)
        try:
            result = run(['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'],
                         timeout=120, check=False)
            if result.returncode == 0:
                return
        except subprocess.TimeoutExpired:
            print('APT index update exceeded 120 seconds', flush=True)
    raise RuntimeError('Ubuntu index updates failed on both HTTPS mirrors; package installation stopped')


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
        raise RuntimeError('This setup is only for root on disposable GitHub Actions runners')
    if 'ID=ubuntu' not in Path('/etc/os-release').read_text().splitlines():
        raise RuntimeError('Ubuntu runner required')
    arch = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    prepare(Path('/etc/apt'), arch)


if __name__ == '__main__':
    main()
