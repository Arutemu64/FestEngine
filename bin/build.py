import sys
import os
import subprocess
import time

name = 'FestEngine'
bin_path = os.getcwd()
sources_path = os.path.join('..', 'src')
main_file = 'main.pyw'
appimage_excludelist_url = 'https://raw.githubusercontent.com/AppImage/AppImages/master/excludelist'

pyinst_flags = ['--clean', '-y', main_file]

if not (len(sys.argv) > 1 and '-d' in sys.argv[1:]):  # Debug mode with console window
    pyinst_flags.insert(1, '--windowed')

self_name = os.path.basename(sys.argv[0])
print("--------------- %s started! ---------------" % self_name)

no_vlc = len(sys.argv) > 1 and '-novlc' in sys.argv[1:]
vlc_binaries = []
vlc_path = None

if sys.platform.startswith('linux'):
    pyinst_flags.insert(0, '--strip')

elif sys.platform == "win32" and not no_vlc:
    if len(sys.argv) == 2:
        vlc_path = sys.argv[1]
    elif len(sys.argv) > 2:
        print("Usage: python %s [vlc_path]" % self_name)
        exit(1)
    else:
        try:
            from winreg import *  # Python 3
            with ConnectRegistry(None, HKEY_LOCAL_MACHINE) as reg:
                with OpenKey(reg, "Software\\VideoLAN\\VLC") as key:
                    vlc_path = QueryValueEx(key, "InstallDir")[0]
        except OSError as e:
            print(e)
        else:
            vlc_binaries = {'libvlc.dll': '.',
                            'libvlccore.dll': '.',
                            'plugins': 'plugins'}
            vlc_binaries = {os.path.join(vlc_path, src): tgt for src, tgt in vlc_binaries.items()}
        if not vlc_path or not os.path.isdir(vlc_path):
            import platform

            print("VLC not found. Install the %s VLC or pass the path to VLC as a parameter." %
                  platform.architecture()[0])
            exit(1)
    print("Using VLC installation: %s" % vlc_path)

    vlc_binaries = sum([['--add-binary', '%s;%s' % (src_path, tgt_path)]
                        for src_path, tgt_path in vlc_binaries.items()], [])
else:
    print("Sorry, your platform is not supported")
    exit(1)
dist_path = os.path.abspath(os.curdir)
os.chdir(sources_path)

pyinst_cmd = ['pyinstaller', '-n', name, '--distpath', dist_path] + vlc_binaries + pyinst_flags

print("Running:", " ".join(pyinst_cmd))

p = subprocess.Popen(pyinst_cmd)

t = 0
while p.poll() is None:
    time.sleep(1)
    t += 1
    if t % 20 == 0:
        print("--- Still building... %ds passed." % t)

print("--------------- Built in %ds with exitcode %d! ---------------" % (t, p.poll()))

if p.poll() == 0 and sys.platform.startswith('linux'):
    print("--- Cleaning extra libs according to the AppImage excludelibs list...")
    import urllib.request
    exclude_libs = urllib.request.urlopen(appimage_excludelist_url).read()
    exclude_libs = [e.rsplit('.so', 1)[0] for e in exclude_libs.decode().split('\n') if e and e[0] != '#']
    exclude_libs.append('libharfbuzz')  # https://github.com/AppImage/AppImageKit/issues/454
    os.chdir(os.path.join(bin_path, name))
    all_files = os.listdir()
    libs_to_exclude = list(filter(lambda f: any([f.startswith(l) for l in exclude_libs]), all_files))
    print("--- Removing:", libs_to_exclude)
    [os.remove(lib) for lib in libs_to_exclude]

print("--------------- Ready! ---------------")
