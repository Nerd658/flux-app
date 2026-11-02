// Listes proposées dans le formulaire de demande : ajout, renommage, suppression
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import { ConfirmDialog, ErrorBanner, Loading, PageHero, useToast } from "../../components/ui.jsx";
import { IconLock, IconPencil, IconPlus, IconTrash } from "../../components/icons.jsx";

const KINDS = [
  { key: "flux-types", label: "Types d'ouverture", unit: ["demande", "demandes"], hint: "Proposés à la première étape d'une demande. Un type déjà utilisé se renomme mais ne se supprime pas." },
  { key: "directions", label: "Directions", unit: ["demande", "demandes"], hint: "Direction du demandeur, également attribuée aux comptes utilisateurs." },
  { key: "zones", label: "Zones", unit: ["flux", "flux"], hint: "Zones réseau de la source et de la destination. Le type d'accès d'un flux en découle : « zone source - zone destination »." },
  { key: "pays", label: "Pays", unit: ["flux", "flux"], hint: "Avec une seule valeur, le pays est rempli automatiquement et masqué dans le formulaire." },
];

export default function AdminReferentials() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState(KINDS[0].key);
  const [label, setLabel] = useState("");
  const [mgrCuid, setMgrCuid] = useState("");
  const [editing, setEditing] = useState(null); // { id, value, manager_cuid }
  const [toDelete, setToDelete] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.admin.referentiels().then(setData).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const kind = KINDS.find((k) => k.key === tab);
  const items = data?.[tab] || [];
  const usageText = (n) => (n ? `Utilisé dans ${n} ${n > 1 ? kind.unit[1] : kind.unit[0]}` : "Pas encore utilisé");

  function switchTab(key) {
    setTab(key);
    setLabel("");
    setMgrCuid("");
    setEditing(null);
    setError("");
  }

  async function add(e) {
    e.preventDefault();
    const value = label.trim();
    if (value.length < 2) return;
    setBusy(true);
    setError("");
    try {
      await api.admin.addRef(tab, value, tab === "directions" ? mgrCuid.trim().toUpperCase() : null);
      setLabel("");
      setMgrCuid("");
      toast(`« ${value} » ajouté à la liste ${kind.label}`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function rename(e) {
    e.preventDefault();
    const value = editing.value.trim();
    if (value.length < 2) return;
    setBusy(true);
    setError("");
    try {
      await api.admin.renameRef(
        tab,
        editing.id,
        value,
        tab === "directions" ? editing.manager_cuid?.trim().toUpperCase() : null
      );
      setEditing(null);
      toast(`Valeur mise à jour`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const closeDelete = useCallback(() => setToDelete(null), []);

  return (
    <div>
      <PageHero kicker="Administration" title="Référentiels"
                lead="Les listes proposées dans le formulaire de demande. Chaque changement s'applique immédiatement à tous les utilisateurs." />

      <ErrorBanner title="Modification impossible" message={error} />

      <section className="table-card">
        <div className="tabs" role="tablist" aria-label="Listes">
          {KINDS.map((k) => (
            <button key={k.key} type="button" role="tab" aria-selected={tab === k.key}
                    className={`tab ${tab === k.key ? "on" : ""}`} onClick={() => switchTab(k.key)}>
              {k.label}<span className="count num">{data ? data[k.key].length : "–"}</span>
            </button>
          ))}
        </div>

        <div className="ref-head">
          <p>{kind.hint}</p>
          <form className="ref-add" onSubmit={add}>
            <input className="text-input" maxLength={40} placeholder="Saisir une nouvelle valeur" value={label}
                   onChange={(e) => setLabel(e.target.value)} aria-label={`Nouvelle valeur : ${kind.label}`} />
            {tab === "directions" && (
              <input className="text-input upper-value" maxLength={32} placeholder="CUID Manager (ex. MGR0001)"
                     value={mgrCuid} onChange={(e) => setMgrCuid(e.target.value.replace(/[^A-Za-z0-9]/g, ""))}
                     aria-label="CUID du manager de département" style={{ maxWidth: "200px" }} />
            )}
            <button className="btn btn-primary" disabled={busy || label.trim().length < 2}>
              <IconPlus width={18} height={18} />Ajouter
            </button>
          </form>
        </div>

        {!data ? <Loading /> : (
          <ul className="ref-list">
            {items.map((it) => {
              const locked = tab === "flux-types" && it.usage > 0;
              return (
                <li key={it.id} className="ref-item">
                  {editing?.id === it.id ? (
                    <form className="ref-edit" onSubmit={rename}>
                      <input className="text-input" autoFocus maxLength={40} value={editing.value} aria-label="Nouveau libellé"
                             onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                             onKeyDown={(e) => e.key === "Escape" && setEditing(null)} />
                      {tab === "directions" && (
                        <input className="text-input upper-value" maxLength={32} placeholder="CUID Manager"
                               value={editing.manager_cuid || ""}
                               onChange={(e) => setEditing({ ...editing, manager_cuid: e.target.value.replace(/[^A-Za-z0-9]/g, "") })}
                               style={{ maxWidth: "160px" }} aria-label="CUID Manager" />
                      )}
                      <button className="btn btn-primary btn-sm" disabled={busy || editing.value.trim().length < 2}>Enregistrer</button>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(null)}>Annuler</button>
                    </form>
                  ) : (
                    <>
                      <span className="ref-label">
                        {it.libelle}
                        {tab === "directions" && (
                          <small className="field-hint" style={{ display: "inline-block", marginLeft: "12px" }}>
                            Responsable CUID : <strong>{it.manager_cuid ? it.manager_cuid : "Non assigné"}</strong>
                          </small>
                        )}
                      </span>
                      <span className={`ref-usage ${it.usage ? "used" : ""}`}>{usageText(it.usage)}</span>
                      <div className="row-actions">
                        <button type="button" className="icon-btn" title="Modifier" aria-label={`Modifier ${it.libelle}`}
                                onClick={() => setEditing({ id: it.id, value: it.libelle, manager_cuid: it.manager_cuid || "" })}><IconPencil /></button>
                        <button type="button" className="icon-btn danger" aria-label={`Supprimer ${it.libelle}`}
                                disabled={items.length <= 1 || locked}
                                title={items.length <= 1 ? "La liste doit garder au moins une valeur" : locked ? "Déjà utilisé : renommez-le plutôt" : "Supprimer"}
                                onClick={() => setToDelete(it)}><IconTrash /></button>
                      </div>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <p className="card-foot-note">
          <IconLock width={16} height={16} />
          Les demandes déjà envoyées conservent le libellé d'origine : leur contenu est scellé.
        </p>
      </section>

      {toDelete && (
        <ConfirmDialog
          title={`Supprimer « ${toDelete.libelle} » ?`}
          confirmLabel="Supprimer"
          tone="danger"
          onClose={closeDelete}
          onConfirm={async () => {
            await api.admin.deleteRef(tab, toDelete.id);
            toast(`« ${toDelete.libelle} » supprimé`, "info");
            setToDelete(null);
            await load();
          }}
        >
          <p>
            Cette valeur ne sera plus proposée dans les formulaires.
            {toDelete.usage ? ` Les ${toDelete.usage} ${toDelete.usage > 1 ? kind.unit[1] : kind.unit[0]} qui l'utilisent la conservent.` : ""}
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
