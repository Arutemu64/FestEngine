import os
import threading
import time

import vlc
import wx
import wx.grid

from constants import Colors, FileTypes


class BackgroundMusicPlayer(object):
    def __init__(self, parent):
        self.parent = parent

        self.timer_update_ms = 500
        self.volume = 50
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.player.audio_set_volume(self.volume)
        self.player.audio_set_mute(False)
        self.window = None
        self.playlist = None
        self.current_track_i = -1
        self.fade_in_out = True
        self.stop_fade_speed = 0.05
        self.pause_fade_speed = 0.01

    def window_exists(self):
        return bool(self.window)

    def show_window(self):
        if not self.window_exists():
            self.window = BackgroundMusicFrame(self.parent)
        self.window.Show()
        self.window.fade_in_out_switch.SetValue(self.fade_in_out)
        self.window.vol_slider.SetValue(self.volume)
        self.window.set_volume_from_slider()
        if self.playlist:
            self.load_playlist_to_grid()

        if self.player.get_state() in {vlc.State.Playing, vlc.State.Paused}:
            self.window.lock_btn.Enable(True)

    def load_files(self, bg_music_dir):
        file_paths = [os.path.join(bg_music_dir, f) for f in sorted(os.listdir(bg_music_dir))]
        self.playlist = [{'title': os.path.basename(p).rsplit('.', 1)[0],
                          'path': p,
                          'color': Colors.BG_NEVER_PLAYED}
                         for p in file_paths if os.path.isfile(p) and os.path.basename(p).rsplit('.', 1)[1] in FileTypes.audio_extensions]
        if self.window_exists():
            self.load_playlist_to_grid()

    def load_playlist_to_grid(self):
        if self.window.grid.GetNumberRows() > 0:
            self.window.grid.DeleteRows(0, self.window.grid.GetNumberRows(), False)
        self.window.grid.AppendRows(len(self.playlist))
        for i in range(len(self.playlist)):
            self.window.grid.SetCellValue(i, 0, self.playlist[i]['title'])
            self.window.grid.SetReadOnly(i, 0)
            self.window.grid.SetCellBackgroundColour(i, 0, self.playlist[i]['color'])
        self.window.grid.AutoSize()
        self.window.Layout()
        self.window.play_btn.Enable(True)
        player_state = self.parent.bg_player.player.get_state()
        if player_state in range(5):  # If playing
            self.window.pause_btn.SetValue(player_state == vlc.State.Paused)

    def switch_track_async(self, from_grid=True):
        threading.Thread(target=self.switch_track_sync, args=(from_grid,)).start()
        self.parent.bg_player_timer_start(self.timer_update_ms)

    def switch_track_sync(self, from_grid=True):
        if not self.playlist:
            return
        if self.current_track_i >= 0:
            if self.player.get_state() in {vlc.State.Playing, vlc.State.Paused}:
                self.playlist[self.current_track_i]['color'] = Colors.BG_SKIPPED
                if self.fade_in_out:
                    self.fade_out_sync(self.stop_fade_speed)  # Blocks thread
            else:
                self.playlist[self.current_track_i]['color'] = Colors.BG_PLAYED_TO_END
        if self.window_exists():
            self.window.grid.SetCellBackgroundColour(self.current_track_i, 0,
                                                     self.playlist[self.current_track_i]['color'])
            self.window.grid.ForceRefresh()  # Updates colors

        if self.window_exists() and from_grid:
            self.current_track_i = self.window.grid.GetSelectedRows()[0]
        else:
            self.current_track_i = (self.current_track_i + 1) % len(self.playlist)

        self.parent.bg_player.play_sync()
        self.parent.bg_pause_switch.Enable(True)

    def _fade_sync(self, vol_range, delay):
        window_exists = self.window_exists()
        if window_exists:
            wx.CallAfter(lambda: self.window.vol_slider.Enable(False))

        vol_msg = ''
        for i in vol_range:
            self.player.audio_set_volume(i)
            vol_msg = 'Vol: %d' % self.player.audio_get_volume()
            wx.CallAfter(lambda: self.parent.set_bg_player_status('Fading %s... %s' %
                                                                  ('in' if vol_range[0] < vol_range[-1] else 'out',
                                                                   vol_msg)))
            if window_exists:
                def ui_upd():
                    self.window.vol_slider.SetValue(i)
                    self.window.vol_label.SetLabel("FAD: %d" % i)
                wx.CallAfter(ui_upd)
            time.sleep(delay)

        wx.CallAfter(lambda: self.parent.set_bg_player_status(vol_msg))

        if window_exists:
            def ui_upd():
                self.window.vol_slider.Enable(True)
                self.window.vol_label.SetLabel("VOL: %d" % i)
            wx.CallAfter(ui_upd)

    def fade_in_sync(self, delay):
        self._fade_sync(range(0, self.volume + 1, 1), delay)

    def fade_out_sync(self, delay):
        self._fade_sync(range(self.volume, -1, -1), delay)

    def play_sync(self):
        self.player.set_media(self.vlc_instance.media_new(self.playlist[self.current_track_i]['path']))
        if self.player.play() != 0:  # [Play] button is pushed here!
            wx.CallAfter(lambda: self.parent.set_bg_player_status("Playback FAILED !!!"))
            return

        state = self.player.get_state()
        start = time.time()
        while state != vlc.State.Playing:
            state = self.player.get_state()
            status = "%s [%fs]" % (self.parent.player_state_parse(state), (time.time() - start))
            wx.CallAfter(lambda: self.parent.set_bg_player_status(status))
            time.sleep(0.005)

        self.playlist[self.current_track_i]['color'] = Colors.BG_PLAYING_NOW

        if self.window_exists():
            def ui_upd():
                self.window.pause_btn.Enable(True)
                self.window.lock_btn.Enable(True)
                self.window.grid.SetCellBackgroundColour(self.current_track_i, 0, Colors.BG_PLAYING_NOW)
                self.window.grid.ForceRefresh()  # Updates colors
                self.window.pause_btn.SetValue(False)

            wx.CallAfter(ui_upd)

        volume = 0 if self.fade_in_out else self.volume
        start = time.time()
        while self.player.audio_get_volume() != volume:
            self.player.audio_set_mute(False)
            self.player.audio_set_volume(volume)
            status = "Trying to unmute... [%fs]" % (time.time() - start)
            wx.CallAfter(lambda: self.parent.set_bg_player_status(status))
            time.sleep(0.005)

        if self.fade_in_out:
            self.fade_in_sync(self.stop_fade_speed)

        wx.CallAfter(lambda: self.parent.set_bg_player_status("%s Vol:%d" %
                                                              (self.parent.player_state_parse(self.player.get_state()),
                                                               self.player.audio_get_volume())))

    def pause_async(self, paused):
        if not self.playlist:
            return
        threading.Thread(target=self.pause_sync, args=(paused,)).start()
        if not paused:
            self.parent.bg_player_timer_start(self.timer_update_ms)

    def pause_sync(self, paused):
        if self.fade_in_out and paused:
            self.fade_out_sync(self.pause_fade_speed)
        self.player.set_pause(paused)
        if self.fade_in_out and not paused:
            self.fade_in_sync(self.pause_fade_speed)


# |  ^
#    |  |
# [MainFrame]
#    |  |
#    v  |


class BackgroundMusicFrame(wx.Frame):
    def __init__(self, parent):
        self.parent = parent
        wx.Frame.__init__(self, parent, title='Background Music Player', size=(400, 500))
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_FRAMEBK))

        # ---------------------------------------------- Layout -----------------------------------------------------
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.top_toolbar = wx.BoxSizer(wx.HORIZONTAL)
        toolbar_base_height = 20

        self.fade_in_out_switch = wx.CheckBox(self, label='FAD')
        self.top_toolbar.Add(self.fade_in_out_switch, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=3)
        self.fade_in_out_switch.Bind(wx.EVT_CHECKBOX, self.parent.fade_switched)

        self.play_btn = wx.Button(self, label="Play", size=(70, toolbar_base_height + 2))
        self.play_btn.Enable(False)
        self.top_toolbar.Add(self.play_btn, 0)
        self.play_btn.Bind(wx.EVT_BUTTON, parent.background_play)
        # Forwarding events through the main window, because this frame is optional and may be absent.

        self.pause_btn = wx.ToggleButton(self, label="Pause", size=(70, toolbar_base_height + 2))

        try:
            self.pause_btn.Enable(self.parent.bg_player.player.get_state() in range(5))
        except AttributeError:
            self.pause_btn.Enable(False)

        self.top_toolbar.Add(self.pause_btn, 0)
        self.pause_btn.Bind(wx.EVT_TOGGLEBUTTON, parent.background_pause)

        self.vol_slider = wx.Slider(self, value=0, minValue=0, maxValue=150)
        self.top_toolbar.Add(self.vol_slider, 1, wx.EXPAND)
        self.vol_slider.Bind(wx.EVT_SLIDER, self.set_volume_from_slider)

        self.vol_label = wx.StaticText(self, label='VOL', size=(50, -1), style=wx.ALIGN_LEFT)
        self.top_toolbar.Add(self.vol_label, 0, wx.ALIGN_CENTER_VERTICAL)

        # --- Table ---
        self.grid = wx.grid.Grid(self)
        self.grid.CreateGrid(0, 1)
        self.grid.HideColLabels()
        self.grid.DisableDragRowSize()
        self.grid.SetRowLabelSize(20)
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)

        def select_row(e):
            row = e.Row if hasattr(e, 'Row') else e.TopRow
            self.grid.Unbind(wx.grid.EVT_GRID_RANGE_SELECT)
            self.grid.SelectRow(row)
            self.grid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, select_row)

        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, select_row)
        self.grid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, select_row)

        # --- Time Slider ---

        self.bottom_toolbar = wx.BoxSizer(wx.HORIZONTAL)

        self.lock_btn = wx.ToggleButton(self, label="LOC", size=(35, -1))
        self.bottom_toolbar.Add(self.lock_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        self.lock_btn.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self.time_slider.Enable(not e.Int))
        self.lock_btn.SetValue(True)
        self.lock_btn.Enable(False)

        self.time_slider = wx.Slider(self, value=0, minValue=0, maxValue=1)
        self.bottom_toolbar.Add(self.time_slider, 1, wx.EXPAND)
        self.time_slider.Enable(False)
        self.time_slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self.parent.on_bg_seek)
        self.time_slider.Bind(wx.EVT_COMMAND_SCROLL_THUMBTRACK, self.on_seeking)

        self.time_label = wx.StaticText(self, label='Stopped', size=(50, -1), style=wx.ALIGN_CENTER)
        self.bottom_toolbar.Add(self.time_label, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(self.top_toolbar, 0, wx.EXPAND)
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.TOP, border=1)
        main_sizer.Add(self.bottom_toolbar, 0, wx.EXPAND)

        self.SetSizer(main_sizer)
        self.Layout()

        self.Bind(wx.EVT_CLOSE, parent.on_bg_player_win_close)

    def set_volume_from_slider(self, e=None):
        self.parent.background_volume = self.vol_slider.GetValue()  # Forwards to player
        self.vol_label.SetLabel('VOL: %d' % self.parent.background_volume)  # Gets from player

    def on_seeking(self, e):
        self.parent.bg_player_timer_start(False)
        self.parent.on_background_timer(seeking_time=e.Int)
