import os
import time

import vlc
import wx
import wx.grid


class BackgroundMusicPlayer(object):
    def __init__(self, parent):
        self.parent = parent
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.player.audio_set_volume(50)
        self.player.audio_set_mute(False)
        self.window = BackgroundMusicFrame(self.parent)  # None
        self.playlist = None
        self._current_track_i = -1
        self.fade_in_out = True

    def window_exists(self):
        return isinstance(self.window, BackgroundMusicFrame)

    def show_window(self):
        if not self.window_exists():
            self.window = BackgroundMusicFrame(self.parent)
        self.window.Show()
        self.window.fade_in_out_switch.SetValue(self.fade_in_out)
        self.window.vol_slider.SetValue(self.player.audio_get_volume())
        self.window.set_volume_from_slider()
        if self.playlist:
            self.load_playlist_to_grid()

    def load_files(self, dir):
        file_names = sorted(os.listdir(dir))
        self.playlist = [{'title': f.rsplit('.', 1)[0], 'path': os.path.join(dir, f)} for f in file_names]
        if self.window_exists():
            self.load_playlist_to_grid()

    def load_playlist_to_grid(self):
        if self.window.grid.GetNumberRows() > 0:
            self.window.grid.DeleteRows(0, self.window.grid.GetNumberRows(), False)
        self.window.grid.AppendRows(len(self.playlist))
        for i in range(len(self.playlist)):
            self.window.grid.SetCellValue(i, 0, self.playlist[i]['title'])
            self.window.grid.SetReadOnly(i, 0)
        self.window.grid.AutoSize()
        self.window.Layout()
        self.window.play_btn.Enable(True)

    def select_track(self):
        if not self.playlist:
            return
        if self.window_exists():
            self._current_track_i = self.window.grid.GetSelectedRows()[0]
        else:
            self._current_track_i = (self._current_track_i + 1) % len(self.playlist)
        return self._current_track_i

    def play(self):
        if not self.playlist:
            return

        self.player.set_media(self.vlc_instance.media_new(self.playlist[self.select_track()]['path']))
        if self.player.play() != 0:  # [Play] button is pushed here!
            return

        state = self.player.get_state()
        start = time.time()
        while state != vlc.State.Playing:
            state = self.player.get_state()
            status = "%s [%fs]" % (self.parent.player_state_parse(state), (time.time() - start))
            self.parent.bg_player_status(status)
            time.sleep(0.005)

        # self.timer.Start(500)
        self.window.pause_btn.Enable(True)

        volume = 0 if self.fade_in_out else self.window.vol_slider.GetValue()
        start = time.time()
        while self.player.audio_get_volume() != volume:
            self.player.audio_set_mute(False)
            self.player.audio_set_volume(volume)
            status = "Trying to unmute... [%fs]" % (time.time() - start)
            self.parent.bg_player_status(status)
            time.sleep(0.002)

        if self.fade_in_out:
            for i in range(0, self.window.vol_slider.GetValue(), 1):
                self.player.audio_set_volume(i)
                vol_msg = 'Vol: %d' % self.player.audio_get_volume()
                self.parent.bg_player_status('Fading in... ' + vol_msg)
                time.sleep(0.05)

        self.parent.bg_player_status("%s Vol:%d" %
                                     (self.parent.player_state_parse(self.player.get_state()),
                                      self.player.audio_get_volume()))

    def pause(self, paused):
        if not self.playlist:
            return

        if self.fade_in_out:
            pass
        pass


class BackgroundMusicFrame(wx.Frame):
    def __init__(self, parent):
        self.parent = parent
        wx.Frame.__init__(self, parent, title='Background Music Player', size=(400, 500))
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_FRAMEBK))

        # ---------------------------------------------- Layout -----------------------------------------------------
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.toolbar = wx.BoxSizer(wx.HORIZONTAL)
        toolbar_base_height = 20

        self.fade_in_out_switch = wx.CheckBox(self, label='FAD')
        self.toolbar.Add(self.fade_in_out_switch, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=3)
        self.fade_in_out_switch.Bind(wx.EVT_CHECKBOX, self.parent.fade_switched)

        self.play_btn = wx.Button(self, label="Play", size=(70, toolbar_base_height + 2))
        self.play_btn.Enable(False)
        self.toolbar.Add(self.play_btn, 0)
        self.play_btn.Bind(wx.EVT_BUTTON, parent.background_play)
        # Forwarding events through the main window, because this frame is optional and may be absent.

        self.pause_btn = wx.ToggleButton(self, label="Pause", size=(70, toolbar_base_height + 2))
        self.pause_btn.Enable(False)
        self.toolbar.Add(self.pause_btn, 0)
        self.pause_btn.Bind(wx.EVT_TOGGLEBUTTON, parent.background_pause)

        self.vol_slider = wx.Slider(self, value=0, minValue=0, maxValue=150)
        self.toolbar.Add(self.vol_slider, 1, wx.EXPAND)
        self.vol_slider.Bind(wx.EVT_SLIDER, self.set_volume_from_slider)

        self.vol_label = wx.StaticText(self, label='VOL', size=(50, -1), style=wx.ALIGN_LEFT)
        self.toolbar.Add(self.vol_label, 0, wx.ALIGN_CENTER_VERTICAL)

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

        main_sizer.Add(self.toolbar, 0, wx.EXPAND)
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.TOP, border=1)

        self.SetSizer(main_sizer)
        self.Layout()

    def set_volume_from_slider(self, e=None):
        self.parent.background_volume = self.vol_slider.GetValue()  # Forwards to player
        self.vol_label.SetLabel('VOL: %d' % self.parent.background_volume)  # Gets from player