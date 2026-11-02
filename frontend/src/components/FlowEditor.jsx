// Étape « Flux » : une ligne par flux, une seule dépliée à la fois.
// Flux déplié : Source → Destination côte à côte, puis le service et le type d'accès, puis la justification.
import { Field } from "./ui.jsx";
import { IconChevronRight, IconCopy, IconPlus, IconTrash } from "./icons.jsx";

const PORTS = /^\d{1,5}(-\d{1,5})?(\s*,\s*\d{1,5}(-\d{1,5})?)*$/;
const PROTO = /^[A-Za-z0-9/_-]{2,10}$/;
const REQUIRED = ["src_ip", "src_zone", "src_pays", "src_app", "dst_ip", "dst_zone", "dst_pays", "dst_app"];

// ICMP n'utilise pas de ports : le champ est alors sans objet (règle identique côté serveur)
export const isIcmp = (l) => l.protocole.trim().toUpperCase() === "ICMP";

// Type d'accès = « zone source - zone destination » : affiché ici, recalculé et enregistré par le serveur
export const accessType = (l) => (l.src_zone && l.dst_zone ? `${l.src_zone} - ${l.dst_zone}` : "");

// Validation côté client : confort de saisie uniquement, le serveur reste l'autorité
export function validateLine(l) {
  const e = {};
  REQUIRED.forEach((k) => { if (!String(l[k]).trim()) e[k] = "Requis"; });
  if (!PROTO.test(l.protocole.trim())) e.protocole = l.protocole.trim() ? "Lettres, chiffres, / ou -" : "Requis";
  if (!isIcmp(l)) {
    const ports = l.dst_ports.trim();
    if (!ports) e.dst_ports = "Requis";
    else if (!PORTS.test(ports)) e.dst_ports = "Format : 443 ou 8080-8090";
  }
  if (accessType(l).length > 80) e.type_acces = "Noms de zones trop longs";
  if (l.justification.trim().length < 5) e.justification = "5 caractères minimum";
  return e;
}

export function validateLines(lines) {
  const out = {};
  lines.forEach((l) => {
    const e = validateLine(l);
    if (Object.keys(e).length) out[l._id] = e;
  });
  return out;
}

function Select({ value, onChange, options, invalid, placeholder }) {
  return (
    <select className={`text-input select-input ${invalid ? "invalid" : ""} ${value ? "" : "is-empty"}`}
            value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" disabled>{placeholder}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

// Résumé d'un flux sur une ligne : 10.0.0.5 → 192.168.1.10 · TCP 443
function Summary({ l }) {
  const proto = l.protocole.trim().toUpperCase();
  const service = (isIcmp(l) ? [proto] : [proto, l.dst_ports.trim()]).filter(Boolean).join(" ");
  return (
    <span className="flow-summary">
      <span className={l.src_ip ? "" : "placeholder"}>{l.src_ip || "Source"}</span>
      <span className="flow-arrow-sm" aria-hidden="true">→</span>
      <span className={l.dst_ip ? "" : "placeholder"}>{l.dst_ip || "Destination"}</span>
      {service && <span className="flow-service-tag">{service}</span>}
    </span>
  );
}

function Actions({ onDuplicate, onRemove, canDuplicate, canRemove, index }) {
  return (
    <div className="flow-actions">
      <button type="button" className="icon-btn" onClick={onDuplicate} disabled={!canDuplicate}
              aria-label={`Dupliquer le flux ${index}`} title="Dupliquer"><IconCopy width={18} height={18} /></button>
      <button type="button" className="icon-btn danger" onClick={onRemove} disabled={!canRemove}
              aria-label={`Supprimer le flux ${index}`} title="Supprimer"><IconTrash width={18} height={18} /></button>
    </div>
  );
}

// Bloc Source ou Destination : mêmes champs, même ordre, pour une lecture en miroir
function Endpoint({ kind, l, le, setLine, zones, pays }) {
  const p = kind === "src" ? "src" : "dst";
  const title = kind === "src" ? "Source" : "Destination";
  const lead = kind === "src" ? "D'où part le flux" : "Où arrive le flux";
  return (
    <fieldset className={`endpoint ${p}`}>
      {/* La légende nomme le groupe pour les lecteurs d'écran ; le bandeau visuel est un bloc distinct */}
      <legend className="sr-only">{title}</legend>
      <div className="endpoint-head" aria-hidden="true"><strong>{title}</strong><span>{lead}</span></div>
      <div className="endpoint-body">
        <Field label="Adresse IP" error={le[`${p}_ip`]} hint={le[`${p}_ip`] ? undefined : "Plusieurs adresses : séparez-les par des virgules"}>
          <input className="text-input ip-input" maxLength={500} placeholder="Saisir l'adresse IP" spellCheck={false}
                 value={l[`${p}_ip`]} onChange={(e) => setLine(l._id, `${p}_ip`, e.target.value)} />
        </Field>
        <Field label="Zone" error={le[`${p}_zone`]}>
          <Select value={l[`${p}_zone`]} options={zones} invalid={le[`${p}_zone`]} placeholder="Sélectionner la zone"
                  onChange={(v) => setLine(l._id, `${p}_zone`, v)} />
        </Field>
        <Field label="Application / URL" error={le[`${p}_app`]}>
          <input className="text-input" maxLength={255} placeholder="Saisir l'application ou l'URL"
                 value={l[`${p}_app`]} onChange={(e) => setLine(l._id, `${p}_app`, e.target.value)} />
        </Field>
        {pays.length > 1 && (
          <Field label="Pays" error={le[`${p}_pays`]}>
            <Select value={l[`${p}_pays`]} options={pays} invalid={le[`${p}_pays`]} placeholder="Sélectionner le pays"
                    onChange={(v) => setLine(l._id, `${p}_pays`, v)} />
          </Field>
        )}
      </div>
    </fieldset>
  );
}

export default function FlowEditor({
  lines, errors, zones, pays, openId, setOpenId, setLine, addLine, duplicateLine, removeLine,
}) {
  return (
    <section className="card flow-editor">
      <div className="card-heading split">
        <div>
          <h2>Flux à ouvrir</h2>
          <p>Un flux relie une source à une destination. Cliquez sur une ligne pour la modifier.</p>
        </div>
        <span className="flow-count">{lines.length} flux</span>
      </div>

      <ol className="flow-rows">
        {lines.map((l, i) => {
          const le = errors[l._id] || {};
          const open = l._id === openId;
          const complete = Object.keys(validateLine(l)).length === 0;
          const icmp = isIcmp(l);
          const actions = (
            <Actions index={i + 1} canDuplicate={lines.length < 50} canRemove={lines.length > 1}
                     onDuplicate={() => duplicateLine(l)} onRemove={() => removeLine(l._id)} />
          );

          if (!open) {
            return (
              <li key={l._id} className={`flow-row ${errors[l._id] ? "has-error" : ""}`}>
                <button type="button" className="flow-row-main" onClick={() => setOpenId(l._id)} aria-expanded="false">
                  <span className="flow-index">{i + 1}</span>
                  <Summary l={l} />
                  <span className={`flow-state ${complete ? "ok" : ""}`}>{complete ? "Complet" : "À compléter"}</span>
                  <IconChevronRight className="flow-chevron" width={18} height={18} />
                </button>
                {actions}
              </li>
            );
          }

          return (
            <li key={l._id} className="flow-row open">
              <div className="flow-row-head">
                <span className="flow-index">{i + 1}</span>
                <Summary l={l} />
                {actions}
              </div>

              <div className="flow-body-open">
                <div className="endpoints">
                  <Endpoint kind="src" l={l} le={le} setLine={setLine} zones={zones} pays={pays} />
                  <span className="endpoints-arrow" aria-hidden="true">→</span>
                  <Endpoint kind="dst" l={l} le={le} setLine={setLine} zones={zones} pays={pays} />
                </div>

                <fieldset className="flow-block">
                  <legend>Service et type d'accès</legend>
                  <div className="service-grid">
                    <Field label="Protocole" error={le.protocole}>
                      <input className="text-input upper-value" maxLength={10} placeholder="Saisir le protocole" spellCheck={false}
                             value={l.protocole} onChange={(e) => setLine(l._id, "protocole", e.target.value)} />
                    </Field>
                    <Field label="Port(s)" error={icmp ? undefined : le.dst_ports}>
                      <input className="text-input ip-input" maxLength={255} spellCheck={false} disabled={icmp}
                             placeholder={icmp ? "Sans objet pour ICMP" : "Saisir le ou les ports"}
                             value={icmp ? "" : l.dst_ports} onChange={(e) => setLine(l._id, "dst_ports", e.target.value)} />
                    </Field>
                    <Field label={<>Type d'accès <span className="auto-tag">Automatique</span></>} error={le.type_acces}>
                      <input className="text-input computed" readOnly tabIndex={-1} value={accessType(l)}
                             placeholder="Déduit des deux zones" />
                    </Field>
                  </div>
                </fieldset>

                <fieldset className="flow-block">
                  <legend>Justification</legend>
                  <Field label="Pourquoi ce flux est-il nécessaire ?" error={le.justification}>
                    <textarea className="text-input" rows={3} maxLength={2000} placeholder="Saisir la justification de la demande"
                              value={l.justification} onChange={(e) => setLine(l._id, "justification", e.target.value)} />
                  </Field>
                </fieldset>
              </div>
            </li>
          );
        })}
      </ol>

      <button type="button" className="add-flow" onClick={addLine} disabled={lines.length >= 50}>
        <IconPlus width={18} height={18} />Ajouter un flux
      </button>
    </section>
  );
}
