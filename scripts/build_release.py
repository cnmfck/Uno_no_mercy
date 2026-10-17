"""Build, verify, and archive a native release on the current OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'UNO-No-Mercy'


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='v6.0.0')
    parser.add_argument('--label', help='Optional filename suffix for a local build.')
    parser.add_argument('--headless', action='store_true',
                        help='Check imports, Tcl, and engine without opening a GUI.')
    args = parser.parse_args()
    version = args.version
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', version):
        parser.error('Use a version such as v6.0.0 or v6.0.0-beta.1.')
    if args.label and not re.fullmatch(r'[A-Za-z0-9.-]+', args.label):
        parser.error('The label may contain letters, digits, periods, and hyphens.')
    system = platform.system()
    os_name = {'Windows': 'windows', 'Darwin': 'macos', 'Linux': 'linux'}.get(system)
    machine = platform.machine().lower()
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(machine)
    if not os_name or not arch:
        parser.error(f'Unsupported build platform: {system} {machine}')
    target = f'{os_name}-{arch}'
    stem = f'{NAME}-{version}-{target}' + (f'-{args.label}' if args.label else '')
    work = ROOT / 'build' / target
    dist = ROOT / 'dist' / target
    output = ROOT / 'release-assets'
    for folder in (work, dist, output):
        folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--name', NAME, '--distpath', str(dist),
               '--workpath', str(work / 'pyinstaller'), '--specpath', str(work),
               '--paths', str(ROOT)]
    if system in ('Windows', 'Darwin'):
        command.append('--windowed')
    if system == 'Darwin':
        command.extend(['--osx-bundle-identifier', 'org.unonomercy.fangame'])
    command.append(str(ROOT / 'launcher.py'))
    subprocess.run(command, cwd=ROOT, check=True)

    bundle = dist / (NAME + '.app' if system == 'Darwin' else NAME)
    executable = (bundle / 'Contents' / 'MacOS' / NAME if system == 'Darwin'
                  else bundle / (NAME + '.exe' if system == 'Windows' else NAME))
    report = work / 'native-check.json'
    report.unlink(missing_ok=True)
    subprocess.run([str(executable), '--self-check' if args.headless else '--smoke-test',
                    '--report', str(report)], check=True, timeout=60)
    check = json.loads(report.read_text(encoding='utf-8'))
    if check.get('status') != 'passed' or not check.get('frozen'):
        raise RuntimeError(f'Native build verification failed: {check}')

    # Preserve the macOS app layout and its framework symlinks.
    stage = work / 'package' / stem
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(bundle, stage / bundle.name, symlinks=True)
    for name in ('README.md', 'RELEASE_NOTES.md'):
        shutil.copy2(ROOT / name, stage / name)
    shutil.copy2(report, stage / 'BUILD_CHECK.json')
    if system == 'Windows':
        start = 'Extract the entire ZIP, then open UNO-No-Mercy/UNO-No-Mercy.exe. Keep the _internal folder beside the executable.'
    elif system == 'Darwin':
        start = 'Extract the ZIP and open UNO-No-Mercy.app. Use the archive matching your Mac architecture. This app is not Developer ID signed or notarized; macOS may block its first launch.'
    else:
        start = 'Extract the tar.gz and run ./UNO-No-Mercy/UNO-No-Mercy from the extracted directory. A graphical desktop and compatible system libraries are required.'
    (stage / 'START_HERE.txt').write_text(
        f'UNO No Mercy {version}\nTarget: {target}\n\n{start}\n\n'
        'Python and Tcl/Tk are bundled. The game interface is in Chinese.\n'
        f'Build host: {platform.platform()}\n'
        f'libc: {platform.libc_ver()}\n'
        f'GUI startup checked: {check["graphical"]}\n'
        'Use on trusted LANs only. Network protocol: 6.\n', encoding='utf-8')
    if system == 'Darwin':
        archive = output / (stem + '.zip')
        archive.unlink(missing_ok=True)
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(stage), str(archive)], check=True)
    elif system == 'Windows':
        archive = Path(shutil.make_archive(str(output / stem), 'zip', stage.parent, stage.name))
    else:
        archive = output / (stem + '.tar.gz')
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(stage, arcname=stage.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(
        f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Created {archive}')


if __name__ == '__main__':
    run()
