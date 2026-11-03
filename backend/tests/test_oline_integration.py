from unittest.mock import MagicMock, patch
import pytest

from app.models import FluxRequest, Periode
from app.oline import Oline, OlineError
from app.services.oline_service import OlineService


def test_oline_client_initialization():
    o = Oline(url="http://test.local", api_key="secret123", verify_ssl=True)
    assert o.url == "http://test.local"
    assert o.api_key == "secret123"
    assert o.verify_ssl is True


def test_oline_service_not_configured():
    db = MagicMock()
    req = MagicMock(spec=FluxRequest)
    with patch("app.services.oline_service.Oline") as mock_oline_cls:
        instance = MagicMock()
        instance.url = None
        instance.api_key = None
        mock_oline_cls.return_value = instance

        res = OlineService.sync_ticket_on_final_validation(db, req)
        assert res is None


def test_oline_service_success_with_caller():
    db = MagicMock()
    req = MagicMock(spec=FluxRequest)
    req.id = 42
    req.reference = "FLUX-2026-TEST"
    req.flux_type_label = "Interne"
    req.dem_nom = "Dupont"
    req.dem_prenom = "Jean"
    req.dem_email = "jean.dupont@societe.bf"
    req.dem_telephone = "+226 70 00 00 00"
    req.departement = "Direction Informatique"
    req.mgr_nom = "Durand"
    req.mgr_prenom = "Alice"
    req.mgr_email = "alice.durand@societe.bf"
    req.periode = Periode.permanente
    req.date_debut = "2026-11-01"
    req.date_fin = None
    req.content_hash = "abcdef123456"
    req.lines = []
    req.validations = []

    with patch("app.services.oline_service.Oline") as mock_oline_cls, \
         patch("app.services.request_service.RequestService.to_detail") as mock_to_detail, \
         patch("app.services.oline_service.build_pdf") as mock_build_pdf:

        mock_inst = MagicMock()
        mock_inst.url = "http://itop.test"
        mock_inst.api_key = "token"
        mock_inst.create_ticket.return_value = {"id": 101, "ref": "R-000101"}
        mock_oline_cls.return_value = mock_inst

        mock_build_pdf.return_value = b"%PDF-mock"

        ticket_ref = OlineService.sync_ticket_on_final_validation(db, req)

        assert ticket_ref == "R-000101"
        assert req.ticket_ref == "R-000101"
        mock_inst.create_ticket.assert_called_once_with(
            title="[TEST][Flux] Interne - FLUX-2026-TEST - DUPONT",
            description=mock_oline_cls.return_value.create_ticket.call_args[1]["description"],
            org_id="Direction Informatique",
            caller_id="jean.dupont@societe.bf",
        )
        mock_inst.add_attachment.assert_called_once_with(
            ticket_id=101,
            file_bytes=b"%PDF-mock",
            filename="FLUX-2026-TEST.pdf",
            mimetype="application/pdf",
        )


def test_oline_service_fallback_without_caller():
    db = MagicMock()
    req = MagicMock(spec=FluxRequest)
    req.id = 43
    req.reference = "FLUX-2026-FALLBACK"
    req.flux_type_label = "Interne"
    req.dem_nom = "Inconnu"
    req.dem_prenom = "Paul"
    req.dem_email = "paul.inconnu@societe.bf"
    req.dem_telephone = "+226 70 11 22 33"
    req.departement = "Direction Informatique"
    req.mgr_nom = "Durand"
    req.mgr_prenom = "Alice"
    req.mgr_email = "alice.durand@societe.bf"
    req.periode = Periode.permanente
    req.date_debut = "2026-11-01"
    req.date_fin = None
    req.content_hash = "abcdef123456"
    req.lines = []
    req.validations = []

    with patch("app.services.oline_service.Oline") as mock_oline_cls, \
         patch("app.services.request_service.RequestService.to_detail"), \
         patch("app.services.oline_service.build_pdf", return_value=b"%PDF-mock"):

        mock_inst = MagicMock()
        mock_inst.url = "http://itop.test"
        mock_inst.api_key = "token"

        # Le premier appel avec caller_id échoue (email absent dans iTop)
        mock_inst.create_ticket.side_effect = [
            OlineError("Caller not found in iTop"),
            {"id": 102, "ref": "R-000102"},
        ]
        mock_oline_cls.return_value = mock_inst

        ticket_ref = OlineService.sync_ticket_on_final_validation(db, req)

        assert ticket_ref == "R-000102"
        assert req.ticket_ref == "R-000102"
        assert mock_inst.create_ticket.call_count == 2
        # Deuxième tentative avec caller_id=None
        assert mock_inst.create_ticket.call_args_list[1][1]["caller_id"] is None


def test_oline_service_resilience_on_total_failure():
    db = MagicMock()
    req = MagicMock(spec=FluxRequest)
    req.id = 44
    req.reference = "FLUX-2026-FAIL"
    req.flux_type_label = "Interne"
    req.dem_nom = "Test"
    req.dem_prenom = "Erreur"
    req.dem_email = "erreur@societe.bf"
    req.dem_telephone = "+226 70 99 99 99"
    req.departement = "Direction Informatique"
    req.mgr_nom = "Durand"
    req.mgr_prenom = "Alice"
    req.mgr_email = "alice.durand@societe.bf"
    req.periode = Periode.permanente
    req.date_debut = "2026-11-01"
    req.date_fin = None
    req.content_hash = "abcdef123456"
    req.lines = []
    req.validations = []

    with patch("app.services.oline_service.Oline") as mock_oline_cls:
        mock_inst = MagicMock()
        mock_inst.url = "http://itop.test"
        mock_inst.api_key = "token"
        mock_inst.create_ticket.side_effect = OlineError("Serveur iTop indisponible")
        mock_oline_cls.return_value = mock_inst

        # Ne doit pas lever d'exception pour ne pas bloquer le workflow de validation
        ticket_ref = OlineService.sync_ticket_on_final_validation(db, req)
        assert ticket_ref is None
