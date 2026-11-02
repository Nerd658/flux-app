from unittest.mock import MagicMock, patch

from app.directory import ActiveDirectoryAuthentication, DirectoryUser, ad_authenticate


def test_active_directory_auth_class_success(monkeypatch):
    monkeypatch.setenv("AD_DOMAIN", "CORP")
    monkeypatch.setenv("AD_SERVERS_IP", "10.0.0.1,10.0.0.2")
    monkeypatch.setenv("AD_RESPONSE_TIMOUT", "5")

    ad = ActiveDirectoryAuthentication()
    assert ad.AD_DOMAIN == "CORP"
    assert ad.AD_RESPONSE_TIMEOUT == 5
    assert ad.server_pool is not None

    with patch("app.directory.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.bind.return_value = True
        mock_conn_cls.return_value = mock_conn

        assert ad.authenticate("jdupont", "secret123") is True
        mock_conn_cls.assert_called_once()
        args, kwargs = mock_conn_cls.call_args
        assert kwargs["user"] == "CORP\\jdupont"
        assert kwargs["password"] == "secret123"


def test_active_directory_auth_class_failure(monkeypatch):
    monkeypatch.setenv("AD_DOMAIN", "CORP")
    monkeypatch.setenv("AD_SERVERS_IP", "10.0.0.1")

    ad = ActiveDirectoryAuthentication()
    with patch("app.directory.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.bind.side_effect = Exception("LDAP bind error")
        mock_conn_cls.return_value = mock_conn

        assert ad.authenticate("jdupont", "wrong") is False


def test_active_directory_authenticate_and_fetch(monkeypatch):
    monkeypatch.setenv("AD_DOMAIN", "CORP")
    monkeypatch.setenv("AD_SERVERS_IP", "10.0.0.1")

    ad = ActiveDirectoryAuthentication()
    with patch("app.directory.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.bind.return_value = True

        entry_mock = {
            "sn": MagicMock(value="Dupont"),
            "givenName": MagicMock(value="Jean"),
            "mail": MagicMock(value="jean.dupont@corp.bf"),
            "telephoneNumber": MagicMock(value="+226 70 00 00 00"),
            "department": MagicMock(value="DSI"),
        }
        mock_conn.entries = [entry_mock]
        mock_conn_cls.return_value = mock_conn

        user = ad.authenticate_and_fetch("jdupont", "secret123")
        assert isinstance(user, DirectoryUser)
        assert user.cuid == "jdupont"
        assert user.nom == "Dupont"
        assert user.prenom == "Jean"
        assert user.email == "jean.dupont@corp.bf"
        assert user.departement == "DSI"


def test_ad_authenticate_dispatcher(monkeypatch):
    monkeypatch.setenv("AD_DOMAIN", "CORP")
    monkeypatch.setenv("AD_SERVERS_IP", "10.0.0.1")

    with patch.object(ActiveDirectoryAuthentication, "authenticate_and_fetch") as mock_fetch:
        mock_fetch.return_value = DirectoryUser("USER1", "Nom", "Prenom", "u@corp.bf", "", "DSI")
        res = ad_authenticate("user1", "pwd")
        assert res.cuid == "USER1"
        mock_fetch.assert_called_once_with("user1", "pwd")
