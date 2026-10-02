from videodl import startup


def test_enable_creates_startup_shortcut_via_powershell(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.enable(run=lambda cmd, **kwargs: commands.append(cmd))
    expected = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Video Downloader.lnk"
    [cmd] = commands
    assert cmd[:2] == ["powershell", "-NoProfile"]
    assert str(expected) in cmd[-1]
    assert "-m videodl" in cmd[-1]
    assert expected.parent.is_dir()


def test_install_shortcuts_creates_both(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.install_shortcuts(run=lambda cmd, **kwargs: commands.append(cmd))
    assert len(commands) == 2
    assert str(startup.start_menu_shortcut()) in commands[0][-1]
    assert str(startup.startup_shortcut()) in commands[1][-1]


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
