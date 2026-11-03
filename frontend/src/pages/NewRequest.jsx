import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.js";
import FlowEditor, { validateLines } from "../components/FlowEditor.jsx";
import RequestView from "../components/RequestView.jsx";
import {
  DatePicker, ErrorBanner, Field, Loading, Notice, PageHero, Segmented, SelectWithAdd, daysBetween, todayIso, useToast,
} from "../components/ui.jsx";
import {
  IconArrowLeft, IconCheck, IconCopy, IconGlobe, IconLock, IconPlus, IconServers, IconTag, IconTrash,
} from "../components/icons.jsx";

const STEPS = ["Type d'ouverture", "Informations", "Flux", "Vérification"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE = /^\+?[0-9 ]{8,20}$/;
const TYPE_ICONS = { HA: IconServers, Internet: IconGlobe };

let uid = 0;
const emptyLine = (pays) => ({
  _id: ++uid, // clé locale React, retirée avant envoi
  src_ip: "", src_zone: "", src_pays: pays, src_app: "",
  dst_ip: "", dst_ports: "", protocole: "", dst_zone: "", dst_pays: pays, dst_app: "",
  justification: "",
});

function Stepper({ step }) {
  return (
    <ol className="stepper" aria-label="Étapes de la demande">
      {STEPS.map((s, i) => (
        <li key={s} className={i === step ? "active" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
          <span className="step-dot">{i < step ? <IconCheck width={14} height={14} /> : i + 1}</span>
          <span className="step-label">{s}</span>
        </li>
      ))}
    </ol>
  );
}

function Select({ value, onChange, options, placeholder = "Choisir…", invalid }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={`text-input select-input ${invalid ? "invalid" : ""}`}>
      <option value="" disabled>{placeholder}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

// Validation côté client : confort de saisie uniquement, le serveur reste l'autorité
function validateInfos(f, selectedDir) {
  const e = {};
  if (selectedDir?.managers?.length > 1 && !f.manager_cuid) {
    e.manager_cuid = "Veuillez sélectionner votre responsable de département";
  }
  if (!f.manager.nom.trim()) e.mgr_nom = "Nom requis";
  if (!f.manager.prenom.trim()) e.mgr_prenom = "Prénom requis";
  if (!EMAIL.test(f.manager.email.trim())) e.mgr_email = "Email invalide";
  if (!PHONE.test(f.manager.telephone.trim())) e.mgr_tel = "Format attendu : +226 70 00 00 00";
  if (!f.departement.trim()) e.departement = "Sélectionnez votre direction";
  if (!f.date_debut) e.date_debut = "Choisissez la date de début";
  else if (f.date_debut < todayIso()) e.date_debut = "La date ne peut pas être passée";
  if (f.periode === "temporaire") {
    if (!f.date_fin) e.date_fin = "Choisissez la date de fin";
    else if (f.date_debut && f.date_fin < f.date_debut) e.date_fin = "Doit suivre la date de début";
  }
  return e;
}

// Reprise d'une demande refusée : mêmes informations, dates à confirmer si elles sont passées
function fromRefused(src, ref) {
  const type = ref.flux_types.find((t) => t.libelle === src.flux_type);
  const keep = (d) => (d && d >= todayIso() ? d : "");
  return {
    flux_type_id: type ? type.id : null,
    manager: { ...src.manager },
    manager_cuid: src.manager_cuid || null,
    departement: src.departement,
    periode: src.periode,
    date_debut: keep(src.date_debut),
    date_fin: src.periode === "temporaire" ? keep(src.date_fin) : "",
    lines: src.lines.map(({ numero, ...l }) => ({ ...l, _id: ++uid })),
  };
}

export default function NewRequest() {
  const { user } = useAuth();
  const source = useLocation().state?.from || null;
  const toast = useToast();
  const [ref, setRef] = useState(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState({});
  const [tried, setTried] = useState({}); // étapes déjà soumises : erreurs recalculées à chaque frappe
  const [busy, setBusy] = useState(false);
  const [recap, setRecap] = useState(null);
  const [certified, setCertified] = useState(false);
  const [created, setCreated] = useState(null);
  const [newType, setNewType] = useState("");
  const [addingType, setAddingType] = useState(false);
  const [openId, setOpenId] = useState(null); // flux déplié dans l'étape 3
  const [checkedIds, setCheckedIds] = useState(() => new Set()); // flux déjà vérifiés : seuls eux affichent leurs erreurs

  const [form, setForm] = useState({
    flux_type_id: null,
    manager: { nom: "", prenom: "", email: "", telephone: "" },
    manager_cuid: null,
    departement: "",               // aucune direction imposée : le demandeur choisit
    periode: "temporaire",
    date_debut: "",                // aucune date imposée : le demandeur choisit
    date_fin: "",
    lines: [],
  });

  useEffect(() => {
    api.referentiels()
      .then((r) => {
        setRef(r);
        if (source) {
          const pre = fromRefused(source, r);
          setForm(pre);
          if (pre.flux_type_id) setStep(1);
          return;
        }
        const pays = r.pays.length === 1 ? r.pays[0].libelle : "";
        setForm((f) => ({ ...f, lines: [emptyLine(pays)] }));
      })
      .catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { window.scrollTo(0, 0); }, [step]);

  // À l'arrivée sur l'étape des flux, un flux est toujours déplié
  useEffect(() => {
    if (step === 2 && !form.lines.some((l) => l._id === openId) && form.lines.length) setOpenId(form.lines[0]._id);
  }, [step, form.lines, openId]);

  const selectedDir = ref?.directions?.find((d) => d.libelle === form.departement);

  // Une fois l'étape tentée, les messages d'erreur suivent la saisie en direct
  useEffect(() => {
    if (step === 1 && tried[1]) setErrors(validateInfos(form, selectedDir));
    if (step === 2 && tried[2]) setErrors(validateLines(form.lines));
  }, [form, step, tried, selectedDir]);

  if (!ref) return error ? <ErrorBanner title="Chargement impossible" message={error} /> : <Loading />;

  const zones = ref.zones.map((z) => z.libelle);
  const pays = ref.pays.map((p) => p.libelle);
  const defaultPays = pays.length === 1 ? pays[0] : "";
  const fluxType = ref.flux_types.find((t) => t.id === form.flux_type_id);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const setManager = (k, v) => setForm((f) => ({ ...f, manager: { ...f.manager, [k]: v } }));
  const setLine = (id, k, v) =>
    setForm((f) => ({ ...f, lines: f.lines.map((l) => (l._id === id ? { ...l, [k]: v } : l)) }));
  // Le flux ajouté ou dupliqué devient celui en cours d'édition
  const addLine = () => {
    const l = emptyLine(defaultPays);
    set({ lines: [...form.lines, l] });
    setOpenId(l._id);
  };
  const duplicateLine = (src) => {
    const l = { ...src, _id: ++uid };
    set({ lines: [...form.lines, l] });
    setOpenId(l._id);
  };
  const removeLine = (id) => {
    const rest = form.lines.filter((l) => l._id !== id);
    set({ lines: rest });
    if (openId === id) setOpenId(rest[rest.length - 1]?._id ?? null);
  };

  // Corps envoyé à l'API : uniquement les champs attendus (le backend refuse tout champ en trop)
  const payload = () => {
    const selDir = ref?.directions?.find((d) => d.libelle === form.departement);
    const mgrCuid = form.manager_cuid || (selDir?.managers?.length === 1 ? selDir.managers[0].cuid : selDir?.manager_cuid) || null;
    return {
      flux_type_id: form.flux_type_id,
      manager: form.manager,
      departement: form.departement,
      manager_cuid: mgrCuid,
      periode: form.periode,
      date_debut: form.date_debut,
      date_fin: form.periode === "temporaire" ? form.date_fin || null : null,
      // Champs envoyés listés explicitement : le type d'accès est calculé par le serveur à partir des zones
      lines: form.lines.map((l) => {
        const protocole = l.protocole.trim().toUpperCase();
        return {
          src_ip: l.src_ip, src_zone: l.src_zone, src_pays: l.src_pays, src_app: l.src_app,
          dst_ip: l.dst_ip, dst_zone: l.dst_zone, dst_pays: l.dst_pays, dst_app: l.dst_app,
          protocole, dst_ports: protocole === "ICMP" ? "" : l.dst_ports, // ICMP : pas de port
          justification: l.justification,
        };
      }),
    };
  };

  async function addFluxType() {
    setError("");
    try {
      const t = await api.addFluxType(newType.trim());
      setRef((r) => ({ ...r, flux_types: [...r.flux_types, t].sort((a, b) => a.libelle.localeCompare(b.libelle)) }));
      set({ flux_type_id: t.id });
      setNewType("");
      setAddingType(false);
      toast(`Type « ${t.libelle} » ajouté et disponible pour tous`);
    } catch (e) {
      setError(e.message);
    }
  }

  // Ajoute une direction partagée puis la sélectionne ; renvoie true en cas de succès
  async function addDirection(libelle) {
    setError("");
    try {
      const d = await api.addDirection(libelle);
      setRef((r) => ({ ...r, directions: [...r.directions, d].sort((a, b) => a.libelle.localeCompare(b.libelle)) }));
      set({ departement: d.libelle });
      toast(`Direction « ${d.libelle} » ajoutée et disponible pour tous`);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }

  function next() {
    setError("");
    if (step === 1) {
      setTried((t) => ({ ...t, 1: true }));
      const e = validateInfos(form, selectedDir);
      setErrors(e);
      if (Object.keys(e).length) return;
    }
    if (step === 2) return toRecap();
    setStep(step + 1);
  }

  async function toRecap() {
    setTried((t) => ({ ...t, 2: true }));
    setCheckedIds(new Set(form.lines.map((l) => l._id)));
    const e = validateLines(form.lines);
    setErrors(e);
    if (Object.keys(e).length) {
      setOpenId(form.lines.find((l) => e[l._id])._id); // ouvre le premier flux à corriger
      return;
    }
    setBusy(true);
    try {
      setRecap(await api.preview(payload())); // le récapitulatif affiché est celui validé par le serveur
      setCertified(false);
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    setBusy(true);
    setError("");
    try {
      setCreated(await api.submit(payload()));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  /* ---------- Écran de confirmation ---------- */
  if (created) {
    return (
      <div className="done-screen">
        <span className="done-icon"><IconCheck width={28} height={28} /></span>
        <h1>Demande envoyée</h1>
        <p className="done-ref num">{created.reference}</p>
        <p className="field-hint">Elle est maintenant transmise à votre manager de département (Niveau 1). Vous pouvez suivre chaque étape depuis vos demandes.</p>
        <div className="form-actions center">
          <Link className="btn btn-primary" to={`/demandes/${created.id}`}>Suivre la demande</Link>
          <Link className="btn btn-secondary" to="/nouvelle-demande">Faire une autre demande</Link>
        </div>
      </div>
    );
  }

  const ee = errors;
  const tmp = form.periode === "temporaire";

  return (
    <div className="wizard">
      <PageHero kicker={fluxType && step > 0 ? `Nouvelle demande · ${fluxType.libelle}` : "Nouvelle demande"}
                title="Demande d'ouverture de flux"
                lead={step === 0 ? "Quatre étapes : le type, les informations, les flux, puis une vérification avant l'envoi." : undefined}>
        <Stepper step={step} />
      </PageHero>
      {source && (
        <Notice title={`Reprise de la demande ${source.reference}`}>
          <p>Les informations ont été recopiées. Corrigez ce qui a motivé le refus, puis envoyez la nouvelle demande.</p>
        </Notice>
      )}
      <ErrorBanner message={error} />

      {/* ---------- Étape 1 : type d'ouverture ---------- */}
      {step === 0 && (
        <section className="card">
          <div className="card-heading">
            <div>
              <h2>Quel type d'ouverture demandez-vous ?</h2>
              <p>Choisissez avant de remplir la demande. Si votre cas n'existe pas, ajoutez-le : il sera proposé à tous.</p>
            </div>
          </div>
          <div className="choice-grid" role="radiogroup" aria-label="Type d'ouverture">
            {ref.flux_types.map((t) => {
              const Icon = TYPE_ICONS[t.libelle] || IconTag;
              const on = form.flux_type_id === t.id;
              return (
                <button key={t.id} type="button" role="radio" aria-checked={on}
                        className={`choice-option tile ${on ? "on" : ""}`} onClick={() => set({ flux_type_id: t.id })}>
                  <Icon width={28} height={28} />
                  <span>{t.libelle}</span>
                </button>
              );
            })}
            {addingType ? (
              <div className="choice-option tile adding">
                <input className="text-input" autoFocus maxLength={40} placeholder="Saisir le nom du type" value={newType}
                       onChange={(e) => setNewType(e.target.value)}
                       onKeyDown={(e) => e.key === "Enter" && newType.trim().length >= 2 && addFluxType()} />
                <div className="row">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setAddingType(false); setNewType(""); }}>Annuler</button>
                  <button type="button" className="btn btn-primary btn-sm" disabled={newType.trim().length < 2} onClick={addFluxType}>Ajouter</button>
                </div>
              </div>
            ) : (
              <button type="button" className="choice-option tile dashed" onClick={() => setAddingType(true)}>
                <IconPlus width={28} height={28} />
                <span>Autre type</span>
              </button>
            )}
          </div>
        </section>
      )}

      {/* ---------- Étape 2 : informations ---------- */}
      {step === 1 && (
        <div className="stack">
          <section className="card">
            <div className="card-heading split">
              <div>
                <h2>Demandeur</h2>
                <p>Renseigné depuis votre compte, non modifiable.</p>
              </div>
              <IconLock className="heading-lock" />
            </div>
            <div className="readonly-grid">
              <div><span>Nom</span><strong>{user.nom}</strong></div>
              <div><span>Prénom</span><strong>{user.prenom}</strong></div>
              <div><span>Email</span><strong>{user.email}</strong></div>
              <div><span>Téléphone</span><strong className="num">{user.telephone}</strong></div>
            </div>
            <Field group label="Direction" error={ee.departement} className="narrow-field"
                   hint={ee.departement ? undefined : "Votre direction n'est pas listée ? Choisissez « Ajouter une direction »."}>
              <SelectWithAdd value={form.departement} options={ref.directions.map((d) => d.libelle)} invalid={!!ee.departement}
                             placeholder="Sélectionner la direction" addLabel="+ Ajouter une direction…"
                             inputPlaceholder="Saisir le nom de la direction"
                             onChange={(v) => {
                               const dir = ref.directions.find((d) => d.libelle === v);
                               if (dir?.managers?.length === 1) {
                                 const m = dir.managers[0];
                                 set({
                                   departement: v,
                                   manager_cuid: m.cuid,
                                   manager: {
                                     nom: m.nom,
                                     prenom: m.prenom,
                                     email: m.email,
                                     telephone: m.telephone || form.manager.telephone,
                                   },
                                 });
                               } else if (dir?.managers?.length > 1) {
                                 set({
                                   departement: v,
                                   manager_cuid: "",
                                   manager: { nom: "", prenom: "", email: "", telephone: "" },
                                 });
                               } else {
                                 set({
                                   departement: v,
                                   manager_cuid: dir?.manager_cuid || null,
                                 });
                               }
                             }} onAdd={addDirection} />
            </Field>
          </section>

          <section className="card">
            <div className="card-heading">
              <div>
                <h2>Responsable de département (Manager)</h2>
                <p>
                  {selectedDir?.managers?.length > 1
                    ? "Plusieurs responsables sont habilités pour votre direction. Choisissez le vôtre pour la validation N1."
                    : selectedDir?.managers?.length === 1
                    ? `Responsable désigné pour la direction ${selectedDir.libelle}.`
                    : "Votre responsable hiérarchique de département pour la validation de Niveau 1."}
                </p>
              </div>
            </div>

            {selectedDir?.managers?.length > 1 && (
              <Field group label="Responsable habilité" error={ee.manager_cuid} className="narrow-field"
                     hint="La validation N1 lui sera directement adressée.">
                <select className={`text-input select-input ${ee.manager_cuid ? "invalid" : ""}`}
                        value={form.manager_cuid || ""}
                        onChange={(e) => {
                          const chosen = selectedDir.managers.find((m) => m.cuid === e.target.value);
                          if (chosen) {
                            set({
                              manager_cuid: chosen.cuid,
                              manager: {
                                nom: chosen.nom,
                                prenom: chosen.prenom,
                                email: chosen.email,
                                telephone: chosen.telephone || form.manager.telephone,
                              },
                            });
                          } else {
                            set({
                              manager_cuid: "",
                              manager: { nom: "", prenom: "", email: "", telephone: "" },
                            });
                          }
                        }}>
                  <option value="" disabled>Choisir votre responsable…</option>
                  {selectedDir.managers.map((m) => (
                    <option key={m.cuid} value={m.cuid}>
                      {m.prenom} {m.nom.toUpperCase()} ({m.cuid}) - {m.email}
                    </option>
                  ))}
                </select>
              </Field>
            )}

            <div className="grid-4">
              <Field label="Nom" error={ee.mgr_nom}><input className="text-input" maxLength={100} placeholder="Saisir le nom" value={form.manager.nom} onChange={(e) => setManager("nom", e.target.value)} /></Field>
              <Field label="Prénom" error={ee.mgr_prenom}><input className="text-input" maxLength={100} placeholder="Saisir le prénom" value={form.manager.prenom} onChange={(e) => setManager("prenom", e.target.value)} /></Field>
              <Field label="Email" error={ee.mgr_email}><input className="text-input" type="email" maxLength={255} placeholder="Saisir l'adresse email" value={form.manager.email} onChange={(e) => setManager("email", e.target.value)} /></Field>
              <Field label="Téléphone" error={ee.mgr_tel} hint={ee.mgr_tel ? undefined : "Format +226 70 00 00 00"}><input className="text-input" inputMode="tel" maxLength={20} placeholder="Saisir le numéro de téléphone" value={form.manager.telephone} onChange={(e) => setManager("telephone", e.target.value)} /></Field>
            </div>
          </section>

          <section className="card">
            <div className="card-heading"><div><h2>Période souhaitée</h2><p>Une ouverture temporaire a une date de fin ; une ouverture permanente n'en a pas.</p></div></div>
            <Segmented label="Période" value={form.periode}
                       options={[{ value: "temporaire", label: "Temporaire" }, { value: "permanente", label: "Permanente" }]}
                       onChange={(v) => set({ periode: v, date_fin: v === "permanente" ? "" : form.date_fin })} />
            <div className="date-row">
              <Field group label="Date de début" error={ee.date_debut}>
                <DatePicker label="Date de début" value={form.date_debut} min={todayIso()} invalid={!!ee.date_debut}
                            onChange={(v) => set({ date_debut: v, date_fin: form.date_fin && form.date_fin < v ? "" : form.date_fin })} />
              </Field>
              {tmp ? (
                <Field group label="Date de fin" error={ee.date_fin}>
                  <DatePicker label="Date de fin" value={form.date_fin} min={form.date_debut || todayIso()} invalid={!!ee.date_fin}
                              onChange={(v) => set({ date_fin: v })} />
                </Field>
              ) : (
                <div className="field"><span className="field-label">Date de fin</span><p className="field-hint plain">Aucune : l'ouverture est permanente.</p></div>
              )}
              {tmp && form.date_debut && form.date_fin && form.date_fin >= form.date_debut && (
                <div className="duration"><strong className="num">{daysBetween(form.date_debut, form.date_fin)}</strong> jours d'ouverture</div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* ---------- Étape 3 : flux ---------- */}
      {step === 2 && (
        <FlowEditor
          lines={form.lines} zones={zones}
          errors={Object.fromEntries(Object.entries(ee).filter(([id]) => checkedIds.has(Number(id))))} pays={pays}
          openId={openId} setOpenId={setOpenId} setLine={setLine}
          addLine={addLine} duplicateLine={duplicateLine} removeLine={removeLine}
        />
      )}

      {/* ---------- Étape 4 : vérification ---------- */}
      {step === 3 && recap && (
        <div className="stack">
          <Notice title="Relisez votre demande avant de l'envoyer">
            <p>Une fois envoyée, elle est scellée : son contenu ne peut plus être modifié.</p>
          </Notice>
          <section className="card"><RequestView req={recap} /></section>
          <label className="certify">
            <input type="checkbox" checked={certified} onChange={(e) => setCertified(e.target.checked)} />
            <span>Je certifie que ces flux sont nécessaires à mon activité et que les informations saisies sont exactes.</span>
          </label>
        </div>
      )}

      {/* ---------- Barre d'actions ---------- */}
      <div className="action-bar">
        {step > 0 ? (
          <button type="button" className="btn btn-secondary" onClick={() => { setError(""); setStep(step - 1); }}>
            <IconArrowLeft width={18} height={18} />{step === 3 ? "Modifier" : "Retour"}
          </button>
        ) : <span />}
        <span className="step-count">Étape {step + 1} sur {STEPS.length}</span>
        {step < 3 ? (
          <button type="button" className="btn btn-primary" onClick={next} disabled={busy || (step === 0 && !form.flux_type_id)}>
            {busy ? "Vérification…" : step === 2 ? "Vérifier la demande" : "Continuer"}
          </button>
        ) : (
          <button type="button" className="btn btn-primary" onClick={send} disabled={busy || !certified}>
            {busy ? "Envoi…" : "Envoyer la demande"}
          </button>
        )}
      </div>
    </div>
  );
}
