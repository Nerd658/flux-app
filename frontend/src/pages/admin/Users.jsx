// Comptes : l'administrateur attribue les rôles. L'identité et le mot de passe relèvent de l'annuaire (AD) :
// tout CUID authentifié est demandeur par défaut ; un seul validateur N1 et un seul validateur final à la fois.
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api.js";
import { fullName, initials, ROLE_INFO, useAuth } from "../../auth.js";
import { ConfirmDialog, ErrorBanner, Field, Loading, Modal, Notice, PageHero, useToast } from "../../components/ui.jsx";
import { IconPencil, IconPower, IconSearch, IconUserPlus, IconX } from "../../components/icons.jsx";

const ROLES = ["demandeur", "manager", "securite", "rssi", "admin"];
const ASSIGNABLE = ["manager", "securite", "rssi", "admin"];   // « demandeur » est le rôle par défaut
const STATUT_PRO_LABELS = {
  employe: "Employé",
  prestataire: "Prestataire",
  stagiaire: "Stagiaire",
};
const SINGLE = [];                                             // les validateurs peuvent être plusieurs
const label = (u) => (u.en_attente ? u.cuid : fullName(u));

function RoleOptions({ value, onChange, lockedReason }) {
  return (
    <div className="role-options">
      {ASSIGNABLE.map((r) => (
        <label key={r} className={`role-option ${value === r ? "on" : ""} ${lockedReason ? "disabled" : ""}`}>
          <input type="radio" name="role" value={r} checked={value === r} disabled={!!lockedReason} onChange={() => onChange(r)} />
          <span>
            <strong>{ROLE_INFO[r]?.label || r}</strong>
            <small>{ROLE_INFO[r]?.desc || ""}</small>
          </span>
        </label>
      ))}
      {lockedReason && <span className="field-hint">{lockedReason}</span>}
    </div>
  );
}

// Création (CUID + rôle) ou changement de rôle d'un compte existant
function RoleModal({ initial, isSelf, users, onClose, onSaved }) {
  const creating = !initial;
  const formId = useId();
  const [cuid, setCuid] = useState("");
  const [role, setRole] = useState(ASSIGNABLE.includes(initial?.role) ? initial.role : "manager");
  const [tried, setTried] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const holder = SINGLE.includes(role)
    ? users.find((u) => u.role === role && u.cuid !== (initial?.cuid || cuid.toUpperCase())) : null;
  const cuidError = creating && tried && !/^[A-Za-z0-9]{3,32}$/.test(cuid) ? "3 à 32 lettres ou chiffres" : "";

  async function submit(e) {
    e.preventDefault();
    setTried(true);
    if (creating && !/^[A-Za-z0-9]{3,32}$/.test(cuid)) return;
    setBusy(true);
    setError("");
    try {
      onSaved(creating ? await api.admin.assignRole(cuid.toUpperCase(), role) : await api.admin.setRole(initial.id, role));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <Modal
      size="lg"
      title={creating ? "Attribuer un rôle" : `Rôle de ${label(initial)}`}
      description={creating
        ? "Saisissez le CUID : s'il ne s'est jamais connecté, son nom et sa direction seront repris de l'annuaire."
        : `CUID ${initial.cuid}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>Annuler</button>
          <button type="submit" form={formId} className="btn btn-primary" disabled={busy || (!creating && role === initial.role)}>
            {busy ? "Enregistrement…" : creating ? "Enregistrer" : "Changer le rôle"}
          </button>
        </>
      }
    >
      <form id={formId} className="form-stack" onSubmit={submit} noValidate>
        {creating && (
          <Field label="CUID" error={cuidError}>
            <input className="text-input upper-value" maxLength={32} placeholder="Saisir le CUID" spellCheck={false} autoComplete="off"
                   value={cuid} onChange={(e) => setCuid(e.target.value.replace(/[^A-Za-z0-9]/g, ""))} />
          </Field>
        )}
        <Field group label="Rôle">
          <RoleOptions value={role} onChange={setRole} lockedReason={isSelf ? "Vous ne pouvez pas modifier votre propre rôle." : ""} />
        </Field>
      </form>
      {holder && (
        <Notice tone="warning" title={`${ROLE_INFO[role]?.label || role} actuel : ${label(holder)} (${holder.cuid})`}>
          <p>Ce rôle n'a qu'un titulaire à la fois : {label(holder)} redeviendra demandeur.</p>
        </Notice>
      )}
      <ErrorBanner title="Rôle non enregistré" message={error} />
    </Modal>
  );
}

export default function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [dialog, setDialog] = useState(null); // { type: role | deactivate, user? }
  const close = useCallback(() => setDialog(null), []);

  const load = useCallback(() => api.admin.users().then(setUsers).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const replace = (u) => setUsers((list) => list.map((x) => (x.id === u.id ? u : x)));
  const active = users ? users.filter((u) => u.is_active).length : 0;
  const rows = useMemo(() => {
    if (!users) return null;
    const q = query.trim().toLowerCase();
    return users.filter((u) => (!roleFilter || u.role === roleFilter)
      && (!q || `${u.prenom} ${u.nom} ${u.cuid} ${u.email} ${u.departement}`.toLowerCase().includes(q)));
  }, [users, query, roleFilter]);

  async function reactivate(u) {
    setError("");
    try {
      replace(await api.admin.setStatus(u.id, true));
      toast(`Compte ${u.cuid} réactivé`);
    } catch (e) {
      setError(e.message);
    }
  }

  function saved({ user: u, retires }) {
    const extra = retires.length ? ` ; ${retires.join(", ")} redevient demandeur` : "";
    toast(`${u.cuid} est maintenant ${ROLE_INFO[u.role]?.label || u.role}${extra}`);
    close();
    load();
  }

  return (
    <div>
      <PageHero kicker="Administration" title="Utilisateurs"
                lead={`${users ? `${active} compte${active > 1 ? "s" : ""} actif${active > 1 ? "s" : ""} sur ${users.length}. ` : ""}Tout CUID authentifié est demandeur ; attribuez ici le validateur N1, le validateur final et les administrateurs.`}
                actions={<button type="button" className="btn btn-primary" onClick={() => setDialog({ type: "role" })}>
                  <IconUserPlus width={18} height={18} />Attribuer un rôle
                </button>} />

      <ErrorBanner title="Action impossible" message={error} />

      <section className="table-card">
        <div className="toolbar">
          <label className="search">
            <IconSearch width={18} height={18} />
            <input className="text-input" type="search" placeholder="Rechercher un nom, un CUID, un email…" value={query}
                   onChange={(e) => setQuery(e.target.value)} aria-label="Rechercher un utilisateur" />
          </label>
          <select className={`text-input select-input compact ${roleFilter ? "" : "is-empty"}`} value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filtrer par rôle">
            <option value="">Tous les rôles</option>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_INFO[r]?.label || r}</option>)}
          </select>
        </div>

        {!rows ? <Loading label="Chargement des comptes…" /> : rows.length === 0 ? (
          <div className="empty-state"><strong>Aucun compte ne correspond à ces critères.</strong></div>
        ) : (
          <div className="table-wrap">
            <table className="data-table users-table">
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>CUID</th>
                  <th>Direction</th>
                  <th>Statut pro</th>
                  <th>Rôle</th>
                  <th>État</th>
                  <th className="r"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => {
                  const self = u.id === me.id;
                  const name = label(u);
                  return (
                    <tr key={u.id} className={u.is_active ? "" : "inactive"}>
                      <td>
                        <div className="user-cell">
                          <span className="avatar" aria-hidden="true">{u.en_attente ? u.cuid.slice(0, 2) : initials(u)}</span>
                          <div>
                            <strong>{name}{self && <span className="you">vous</span>}</strong>
                            <small>{u.en_attente ? "En attente de sa première connexion" : u.email}</small>
                          </div>
                        </div>
                      </td>
                      <td><span className="mono">{u.cuid}</span></td>
                      <td>{u.en_attente ? "—" : u.departement}</td>
                      <td>{u.statut_pro ? (STATUT_PRO_LABELS[u.statut_pro] || u.statut_pro) : "—"}</td>
                      <td><span className={`role-pill ${u.role}`}>{ROLE_INFO[u.role]?.label || u.role}</span></td>
                      <td><span className={`state ${u.is_active ? "on" : ""}`}>{u.is_active ? "Actif" : "Désactivé"}</span></td>
                      <td className="r">
                        <div className="row-actions">
                          <button type="button" className="icon-btn" title={self ? "Vous ne pouvez pas modifier votre propre rôle" : "Changer le rôle"}
                                  disabled={self} aria-label={`Changer le rôle de ${name}`}
                                  onClick={() => setDialog({ type: "role", user: u })}><IconPencil /></button>
                          <button type="button" className="icon-btn" disabled={self || u.role === "demandeur"}
                                  title={u.role === "demandeur" ? "Déjà demandeur (rôle par défaut)" : "Retirer le rôle (redevient demandeur)"}
                                  aria-label={`Retirer le rôle de ${name}`}
                                  onClick={() => setDialog({ type: "remove", user: u })}><IconX /></button>
                          {u.is_active ? (
                            <button type="button" className="icon-btn danger" disabled={self}
                                    title={self ? "Vous ne pouvez pas désactiver votre propre compte" : "Bloquer l'accès à l'application"}
                                    aria-label={`Désactiver le compte de ${name}`}
                                    onClick={() => setDialog({ type: "deactivate", user: u })}><IconPower /></button>
                          ) : (
                            <button type="button" className="icon-btn success" title="Réactiver le compte"
                                    aria-label={`Réactiver le compte de ${name}`} onClick={() => reactivate(u)}><IconPower /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Notice tone="info" className="after-table" title="Authentification par l'annuaire">
        <p>Les mots de passe sont ceux de l'Active Directory : l'application n'en crée, n'en modifie ni n'en réinitialise aucun.</p>
      </Notice>

      {dialog?.type === "role" && (
        <RoleModal initial={dialog.user} isSelf={dialog.user?.id === me.id} users={users || []} onClose={close} onSaved={saved} />
      )}
      {dialog?.type === "remove" && (
        <ConfirmDialog
          title={`Retirer le rôle de ${label(dialog.user)} ?`}
          confirmLabel="Retirer le rôle"
          onClose={close}
          onConfirm={async () => saved(await api.admin.setRole(dialog.user.id, "demandeur"))}
        >
          <p>{label(dialog.user)} perd le rôle « {ROLE_INFO[dialog.user.role]?.label || dialog.user.role} » et redevient demandeur, avec effet immédiat.</p>
        </ConfirmDialog>
      )}
      {dialog?.type === "deactivate" && (
        <ConfirmDialog
          title="Bloquer l'accès de ce compte ?"
          confirmLabel="Désactiver"
          tone="danger"
          onClose={close}
          onConfirm={async () => {
            replace(await api.admin.setStatus(dialog.user.id, false));
            toast(`Compte ${dialog.user.cuid} désactivé`, "info");
            close();
          }}
        >
          <p><strong>{label(dialog.user)}</strong> ne pourra plus accéder à l'application, même avec un mot de passe AD valide. Sa session en cours est coupée immédiatement ; ses demandes et décisions restent consultables.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
