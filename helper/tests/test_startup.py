from videodl import startup


def test_enable_creates_startup_shortcut_via_powershell(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.enable(run=lambda cmd, **kwargs: commands.append(cmd))
    expected = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Ragazzo's Downloader.lnk"
    [cmd] = commands
    assert cmd[:2] == ["powershell", "-NoProfile"]
    assert startup._ps_quote(expected) in cmd[-1]
    assert "-m videodl" in cmd[-1]
    assert expected.parent.is_dir()


def test_install_shortcuts_creates_both(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.install_shortcuts(run=lambda cmd, **kwargs: commands.append(cmd))
    assert len(commands) == 2
    assert startup._ps_quote(startup.start_menu_shortcut()) in commands[0][-1]
    assert startup._ps_quote(startup.startup_shortcut()) in commands[1][-1]


def test_is_enabled_and_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    link = startup.startup_shortcut()
    link.parent.mkdir(parents=True)
    link.write_bytes(b"")
    assert startup.is_enabled() is True
    startup.disable()
    assert startup.is_enabled() is False
    startup.disable()  # não falha se já não existe


def test_quotes_apostrophes_for_powershell():
    assert startup._ps_quote("C:\\a'b") == "'C:\\a''b'"


def test_install_shortcuts_removes_old_video_downloader_shortcuts(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    programs = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    old = [programs / "Video Downloader.lnk", programs / "Startup" / "Video Downloader.lnk"]
    for link in old:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_bytes(b"")
    startup.install_shortcuts(run=lambda cmd, **kwargs: None)
    assert not any(link.exists() for link in old)


def test_disable_also_removes_old_startup_shortcut(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    old = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Video Downloader.lnk"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"")
    startup.disable()
    assert not old.exists()
