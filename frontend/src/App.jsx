import { useEffect, useRef, useState } from "react";
import { matchPath, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, SESSION_EXPIRED } from "./api.js";
import { AuthContext, fullName, homeFor, initials, ROLE_INFO, useAuth, VALIDATOR_ROLES } from "./auth.js";
import Login from "./pages/Login.jsx";
import NewRequest from "./pages/NewRequest.jsx";
import MyRequests from "./pages/MyRequests.jsx";
import RequestPage from "./pages/RequestPage.jsx";
import Validation from "./pages/Validation.jsx";
import Verify from "./pages/Verify.jsx";
import AdminDashboard from "./pages/admin/Dashboard.jsx";
import AdminUsers from "./pages/admin/Users.jsx";
import AdminReferentials from "./pages/admin/Referentials.jsx";
import AdminAudit from "./pages/admin/Audit.jsx";
import { ErrorBanner, Field, Modal, ToastProvider, useToast } from "./components/ui.jsx";
import {
  BrandMark, IconChevronDown, IconFileCheck, IconGrid, IconHistory, IconLayers, IconList, IconLogout,
  IconPencil, IconPlus, IconShield, IconUsers,
} from "./components/icons.jsx";

// Menu par rôle : chacun ne voit que ce qu'il a le droit de faire (l'API reste l'autorité)
const VERIFY_SECTION = {
  section: "Contrôle",
  items: [{ to: "/verifier", label: "Vérifier un flux", icon: IconFileCheck }],
};
const VALIDATOR_NAV = [
  { section: "Validation", items: [{ to: "/validation", label: "Demandes à valider", icon: IconShield }] },
  VERIFY_SECTION,
];
const NAV = {
  demandeur: [
    {
      section: "Demandes",
      items: [
        { to: "/nouvelle-demande", label: "Nouvelle demande", icon: IconPlus },
        { to: "/mes-demandes", label: "Mes demandes", icon: IconList },
      ],
    },
    VERIFY_SECTION,
  ],
  manager: VALIDATOR_NAV,
  securite: VALIDATOR_NAV,
  rssi: VALIDATOR_NAV,
  validateur_n1: VALIDATOR_NAV,
  validateur_final: VALIDATOR_NAV,
  admin: [
    {
      section: "Pilotage",
      items: [
        { to: "/admin", label: "Tableau de bord", icon: IconGrid, end: true },
        { to: "/admin/demandes", label: "Toutes les demandes", icon: IconList },
      ],
    },
    {
      section: "Administration",
      items: [
        { to: "/admin/utilisateurs", label: "Utilisateurs", icon: IconUsers },
        { to: "/admin/referentiels", label: "Référentiels", icon: IconLayers },
        { to: "/admin/audit", label: "Journal d'audit", icon: IconHistory },
      ],
    },
    VERIFY_SECTION,
  ],
};

// Fil d'Ariane : [motif, rubrique, page]
const CRUMBS = [
  ["/nouvelle-demande", "Demandes", "Nouvelle demande"],
  ["/mes-demandes", "Demandes", "Mes demandes"],
  ["/validation", "Validation", "Demandes à valider"],
  ["/demandes/:id", "Demandes", "Détail de la demande"],
  ["/verifier", "Contrôle", "Vérification d'authenticité"],
  ["/admin", "Pilotage", "Tableau de bord"],
  ["/admin/demandes", "Pilotage", "Toutes les demandes"],
  ["/admin/utilisateurs", "Administration", "Utilisateurs"],
  ["/admin/referentiels", "Administration", "Référentiels"],
  ["/admin/audit", "Administration", "Journal d'audit"],
];

// Garde de route : l'UI masque, mais c'est l'API qui fait foi (contrôle d'accès côté serveur)
function Guard({ roles, children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/connexion" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return children;
}

// Clé = navigation : chaque clic sur « Nouvelle demande » repart d'un formulaire vierge
function FreshNewRequest() {
  const location = useLocation();
  return <NewRequest key={location.key} />;
}

function Sidebar() {
  const { user } = useAuth();
  const info = ROLE_INFO[user.role] || { label: user.role, desc: "" };
  return (
    <aside className="sidebar" aria-label="Menu">
      <div className="sidebar-top">
        <div className="brand">
          <BrandMark />
          <span className="brand-text"><strong>Flux</strong><small>Orange Burkina · Sécurité SI</small></span>
        </div>
      </div>
      <nav className="main-nav" aria-label="Navigation principale">
        {NAV[user.role].map((group) => (
          <div key={group.section} className="nav-group">
            <div className="sidebar-caption">{group.section}</div>
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className="nav-item">
                <Icon className="nav-icon" /><span>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="scope-card">
          <div className="scope-head">
            <span className="scope-icon"><IconShield width={16} height={16} /></span>
            <div>
              <strong>{info.label}</strong>
              <small>Direction {user.departement}</small>
            </div>
          </div>
          <p>{info.desc}</p>
        </div>
        <small className="sidebar-footer">Département Sécurité des SI</small>
      </div>
    </aside>
  );
}

const STATUT_PRO_LABELS = {
  employe: "Employé",
  prestataire: "Prestataire",
  stagiaire: "Stagiaire",
};

function ProfileModal({ user, force, onClose, onSaved }) {
  const toast = useToast();
  const [nom, setNom] = useState(user.nom && user.nom !== user.cuid ? user.nom : "");
  const [prenom, setPrenom] = useState(user.prenom && user.prenom !== "-" ? user.prenom : "");
  const [email, setEmail] = useState(user.email && !user.email.endsWith("@annuaire.invalid") ? user.email : "");
  const [telephone, setTelephone] = useState(user.telephone || "");
  const [departement, setDepartement] = useState(user.departement && user.departement !== "Non renseignee" ? user.departement : "");
  const [statutPro, setStatutPro] = useState(user.statut_pro || "");
  const [directions, setDirections] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.referentiels().then((r) => setDirections(r.directions || [])).catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    if (!nom.trim() || !prenom.trim() || !email.trim()) {
      setError("Le prénom, le nom et l'adresse email professionnelle sont obligatoires.");
      return;
    }
    if (!departement.trim()) {
      setError("Veuillez sélectionner votre direction de rattachement.");
      return;
    }
    if (!statutPro) {
      setError("Veuillez sélectionner votre statut professionnel (employé, prestataire ou stagiaire).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProfile({
        nom: nom.trim(),
        prenom: prenom.trim(),
        email: email.trim(),
        telephone: telephone.trim(),
        departement: departement.trim(),
        statut_pro: statutPro,
      });
      toast("Profil enregistré avec succès", "success");
      onSaved(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={force ? "Finalisez votre profil" : "Modifier mon profil"}
      description={`CUID ${user.cuid} · Renseignez vos informations pour vos demandes d'ouverture de flux.`}
      onClose={force ? undefined : onClose}
      footer={
        <>
          {!force && (
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>Annuler</button>
          )}
          <button type="submit" form="profile-form" className="btn btn-primary" disabled={busy}>
            {busy ? "Enregistrement…" : "Enregistrer mon profil"}
          </button>
        </>
      }
    >
      <form id="profile-form" className="form-stack" onSubmit={submit}>
        <div className="grid-2">
          <Field label="Prénom">
            <input className="text-input" autoFocus required placeholder="Ex. Jean" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
          </Field>
          <Field label="Nom">
            <input className="text-input" required placeholder="Ex. Dupont" value={nom} onChange={(e) => setNom(e.target.value)} />
          </Field>
        </div>
        <Field label="Email professionnel" hint="Utilisé pour le suivi de vos demandes et vos tickets Oline">
          <input className="text-input" type="email" required placeholder="prenom.nom@orange.com" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <div className="grid-2">
          <Field label="Direction de rattachement" hint="Votre direction dans l'organigramme">
            <select
              className="text-input select-input"
              value={departement}
              onChange={(e) => setDepartement(e.target.value)}
              required
            >
              <option value="" disabled>Sélectionner votre direction…</option>
              {directions.map((d) => (
                <option key={d.id} value={d.libelle}>
                  {d.libelle}
                </option>
              ))}
              {departement && !directions.some((d) => d.libelle === departement) && (
                <option value={departement}>{departement}</option>
              )}
            </select>
          </Field>
          <Field label="Statut professionnel" hint="Votre statut contractuel">
            <select
              className="text-input select-input"
              value={statutPro}
              onChange={(e) => setStatutPro(e.target.value)}
              required
            >
              <option value="" disabled>Sélectionner votre statut…</option>
              <option value="employe">Employé</option>
              <option value="prestataire">Prestataire</option>
              <option value="stagiaire">Stagiaire</option>
            </select>
          </Field>
        </div>
        <Field label="Téléphone">
          <input className="text-input" inputMode="tel" placeholder="+226 70 00 00 00" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
        </Field>
        <ErrorBanner message={error} title="Impossible d'enregistrer" />
      </form>
    </Modal>
  );
}

function UserMenu({ onLogout, onEditProfile }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    ref.current?.querySelector(".menu-item")?.focus();
    const onDoc = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => {
      if (e.key === "Escape") {
        setOpen(false);
        ref.current?.querySelector(".user-trigger")?.focus();
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const items = [...ref.current.querySelectorAll(".menu-item")];
        const i = items.indexOf(document.activeElement);
        items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length]?.focus();
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={ref}>
      <button type="button" className="user-trigger" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="avatar" aria-hidden="true">{initials(user)}</span>
        <span className="user-meta">
          <strong>{fullName(user)}</strong>
          <small>{ROLE_INFO[user.role]?.label || user.role}</small>
        </span>
        <IconChevronDown className="user-chevron" width={16} height={16} />
      </button>
      {open && (
        <div className="menu" role="menu" aria-label="Mon compte">
          <div className="menu-head">
            <strong>{fullName(user)}</strong>
            <small>{user.email}</small>
            <small className="num">CUID {user.cuid}{user.statut_pro ? ` · ${STATUT_PRO_LABELS[user.statut_pro] || user.statut_pro}` : ""}</small>
          </div>
          <button type="button" role="menuitem" className="menu-item" onClick={() => { setOpen(false); onEditProfile(); }} aria-label="Modifier mon profil">
            <IconPencil />Modifier mon profil
          </button>
          <button type="button" role="menuitem" className="menu-item danger" onClick={onLogout} aria-label="Se déconnecter">
            <IconLogout />Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}

function Topbar({ onEditProfile }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const crumb = CRUMBS.find(([p]) => matchPath(p, pathname)) || ["", "", ""];

  async function logout() {
    try {
      await api.logout();
    } finally {
      setUser(null);
      navigate("/connexion");
    }
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <nav className="breadcrumb" aria-label="Fil d'Ariane">
          <span className="crumb-root">{crumb[1]}</span>
          <span className="crumb-separator" aria-hidden="true">/</span>
          <strong>{crumb[2]}</strong>
        </nav>
      </div>
      <UserMenu onLogout={logout} onEditProfile={onEditProfile} />
    </header>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [expired, setExpired] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const userRef = useRef(null);

  useEffect(() => {
    // Restaure la session depuis le cookie HttpOnly (rien n'est stocké côté JS)
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setReady(true));
    const onExpired = () => {
      if (userRef.current) setExpired(true); // message affiché seulement si une session était ouverte
      setUser(null);
    };
    window.addEventListener(SESSION_EXPIRED, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED, onExpired);
  }, []);

  useEffect(() => {
    userRef.current = user;
    if (user) setExpired(false);
  }, [user]);

  if (!ready) return <div className="boot" aria-busy="true" />;

  const mustCompleteProfile = Boolean(user && user.profil_incomplet);

  return (
    <AuthContext.Provider value={{ user, setUser }}>
      <ToastProvider>
        {!user ? (
          <Routes>
            <Route path="/verifier" element={<Verify />} />
            <Route path="*" element={<Login expired={expired} />} />
          </Routes>
        ) : (
          <div className="app-shell">
            <Sidebar />
            <div className="main-content">
              <Topbar onEditProfile={() => setShowProfile(true)} />
              <main className="page-wrap">
                <Routes>
                  <Route path="/connexion" element={<Navigate to={homeFor(user)} replace />} />
                  <Route path="/verifier" element={<Verify />} />
                  <Route path="/nouvelle-demande" element={<Guard roles={["demandeur"]}><FreshNewRequest /></Guard>} />
                  <Route path="/mes-demandes" element={<Guard roles={["demandeur"]}><MyRequests /></Guard>} />
                  <Route path="/validation" element={<Guard roles={VALIDATOR_ROLES}><Validation /></Guard>} />
                  <Route path="/demandes/:id" element={<Guard><RequestPage /></Guard>} />
                  <Route path="/admin" element={<Guard roles={["admin"]}><AdminDashboard /></Guard>} />
                  <Route path="/admin/demandes" element={<Guard roles={["admin"]}><Validation /></Guard>} />
                  <Route path="/admin/utilisateurs" element={<Guard roles={["admin"]}><AdminUsers /></Guard>} />
                  <Route path="/admin/referentiels" element={<Guard roles={["admin"]}><AdminReferentials /></Guard>} />
                  <Route path="/admin/audit" element={<Guard roles={["admin"]}><AdminAudit /></Guard>} />
                  <Route path="*" element={<Navigate to={homeFor(user)} replace />} />
                </Routes>
              </main>
            </div>
            {(mustCompleteProfile || showProfile) && (
              <ProfileModal
                user={user}
                force={mustCompleteProfile}
                onClose={() => setShowProfile(false)}
                onSaved={(updated) => {
                  setUser(updated);
                  setShowProfile(false);
                }}
              />
            )}
          </div>
        )}
      </ToastProvider>
    </AuthContext.Provider>
  );
}
