:: encoding: cp866
cd src
py main.pyw ^
    --filename_re "^(?P<num>\d{3}) (?P<nom>\w{1,2})( \[(?P<start>[GW]{1})\])?\. (?P<name>.*?)(\(.(?P<id>\d{1,3})\))?$" ^
    --background_tracks_dir "D:\Clouds\ownCloud\DATA\���� �����\Yuki no Odori 2016\Fest\background" ^
    --auto_load_files --auto_load_bg --debug_output ^
    "D:\Clouds\ownCloud\DATA\���� �����\Yuki no Odori 2016\Fest\mp3_numbered" ^
    "D:\Clouds\ownCloud\DATA\���� �����\Yuki no Odori 2016\Fest\zad_numbered"

pause