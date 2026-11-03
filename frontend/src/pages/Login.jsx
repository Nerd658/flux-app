import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { homeFor, useAuth } from "../auth.js";
import { Notice } from "../components/ui.jsx";
import { BrandMark, IconEye, IconEyeOff } from "../components/icons.jsx";

export default function Login({ expired = false }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [cuid, setCuid] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await api.login(cuid.trim().toUpperCase(), password);
      setUser(user);
      navigate(homeFor(user), { replace: true });
    } catch (err) {
      setError(err.message);
      setPassword(""); // on ne garde pas le mot de passe en mémoire après un échec
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      {/* Variante A : fond noir à halo orange, présentation à gauche, carte de connexion flottante à droite */}
      <section className="login-pitch">
        <div className="brand">
          <BrandMark />
          <span className="brand-text"><strong>Flux</strong><small>Orange Burkina · Sécurité SI</small></span>
        </div>
        <h1>Plateforme de demande d'ouverture de flux</h1>
        <p>Saisie, double validation, document signé et vérifiable : tout le circuit au même endroit.</p>
        {/* Animation : un paquet qui traverse la route source → destination */}
        <div className="hero-route" aria-hidden="true">
          <span className="node">10.0.0.5</span>
          <span className="wire"><i className="packet" /><em>TCP 443</em></span>
          <span className="node">192.168.1.10</span>
        </div>
      </section>

      <form className="login-card" onSubmit={onSubmit} noValidate>
        <div className="login-title">
          <h2>Connexion</h2>
          <p>Utilisez votre CUID et votre mot de passe applicatif.</p>
        </div>

        {expired && <Notice tone="info" title="Session terminée">Reconnectez-vous pour continuer.</Notice>}

        <label className="field">
          <span className="field-label">CUID</span>
          <input className="text-input upper-value" autoComplete="username" placeholder="Saisir votre CUID" required maxLength={32} autoFocus
                 autoCapitalize="characters" spellCheck={false}
                 value={cuid} onChange={(e) => setCuid(e.target.value.replace(/[^A-Za-z0-9]/g, ""))} />
        </label>

        <label className="field">
          <span className="field-label">Mot de passe applicatif</span>
          <span className="input-affix">
            <input className="text-input" type={show ? "text" : "password"} placeholder="Saisir votre mot de passe applicatif" autoComplete="current-password" required maxLength={128}
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="icon-btn" onClick={() => setShow(!show)}
                    aria-label={show ? "Masquer le mot de passe" : "Afficher le mot de passe"}>
              {show ? <IconEyeOff /> : <IconEye />}
            </button>
          </span>
        </label>

        {error && <Notice tone="error" title="Connexion refusée">{error}</Notice>}

        <button className="btn btn-primary btn-lg block" disabled={busy || cuid.length < 3 || !password}>
          {busy ? "Connexion en cours…" : "Se connecter"}
        </button>
        <p className="login-help">Mot de passe oublié ? Contactez l'administrateur de la plateforme.</p>
        <div style={{ textAlign: "center", marginTop: 16 }}>
          <Link to="/verifier" className="login-verify-link">
            Vérifier l'authenticité d'une demande de flux
          </Link>
        </div>
      </form>
    </div>
  );
}
