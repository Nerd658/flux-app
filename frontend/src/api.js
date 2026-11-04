// Client HTTP : cookie de session HttpOnly envoyé automatiquement, jeton CSRF en en-tête

const FIELD_LABELS = {
  src_ip: "IP source", src_zone: "Zone source", src_pays: "Pays source", src_app: "Application source",
  dst_ip: "IP destination", dst_ports: "Port(s)", protocole: "Protocole", dst_zone: "Zone destination",
  dst_pays: "Pays destination", dst_app: "Application destination", type_acces: "Type d'accès",
  justification: "Justification", nom: "Nom", prenom: "Prénom", email: "Email", telephone: "Téléphone",
  direction: "Direction", departement: "Département", direction_id: "Direction parente",
  date_debut: "Date de début", date_fin: "Date de fin", periode: "Période",
  commentaire: "Commentaire", libelle: "Libellé", password: "Mot de passe applicatif", cuid: "CUID",
  current_password: "Mot de passe actuel", new_password: "Nouveau mot de passe", role: "Rôle",
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// Session expirée ou compte désactivé : l'application revient à l'écran de connexion
export const SESSION_EXPIRED = "flux:session-expired";

function csrfToken() {
  const row = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="));
  return row ? decodeURIComponent(row.split("=")[1]) : "";
}

// Traduit les erreurs 422 de FastAPI en messages lisibles (ex. « Ligne 1 – IP source : ... »)
function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return "Erreur inattendue";
  return detail
    .map(({ loc = [], msg = "" }) => {
      const parts = loc.filter((p) => p !== "body");
      const prefix = [];
      if (parts[0] === "lines" && Number.isInteger(parts[1])) prefix.push(`Ligne ${parts[1] + 1}`);
      if (parts[0] === "manager") prefix.push("Manager");
      const field = parts.find((p) => FIELD_LABELS[p]);
      if (field) prefix.push(FIELD_LABELS[field]);
      const clean = msg.replace(/^Value error, /, "");
      return prefix.length ? `${prefix.join(" – ")} : ${clean}` : clean;
    })
    .join("\n");
}

async function request(path, { method = "GET", body, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/")) window.dispatchEvent(new Event(SESSION_EXPIRED));
    let message = "Erreur serveur";
    try {
      message = formatDetail((await res.json()).detail);
    } catch {
      /* corps non JSON : message générique */
    }
    throw new ApiError(res.status, message);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

const id = (v) => encodeURIComponent(v);
const query = (params) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();

export const api = {
  login: (cuid, password) => request("/auth/login", { method: "POST", body: { cuid, password } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me"),
  updateProfile: (data) => request("/auth/profile", { method: "PUT", body: data }),
  referentiels: () => request("/referentiels"),
  addFluxType: (libelle) => request("/referentiels/flux-types", { method: "POST", body: { libelle } }),
  addDirection: (libelle) => request("/referentiels/directions", { method: "POST", body: { libelle } }),
  addDepartement: (libelle, direction_id, direction_libelle) =>
    request("/referentiels/departements", {
      method: "POST",
      body: { libelle, direction_id: direction_id || null, direction_libelle: direction_libelle || null },
    }),
  preview: (data) => request("/requests/preview", { method: "POST", body: data }),
  submit: (data) => request("/requests", { method: "POST", body: data }),
  mine: () => request("/requests/mine"),
  pending: () => request("/requests/pending"),
  validatorStats: () => request("/requests/validator-stats"),
  all: () => request("/requests/all"),
  get: (rid) => request(`/requests/${id(rid)}`),
  verify: (rid) => request(`/requests/${id(rid)}/verify`),
  publicVerify: (q) => request(`/public/verify?q=${encodeURIComponent(q)}`),
  decide: (rid, decision, commentaire) =>
    request(`/requests/${id(rid)}/decision`, {
      method: "POST",
      body: { decision, commentaire: commentaire || null },
    }),
  async downloadPdf(rid, reference) {
    const res = await request(`/requests/${id(rid)}/pdf`, { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `${reference}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Espace administrateur (l'API refuse tout autre rôle)
  admin: {
    stats: () => request("/admin/stats"),
    users: () => request("/admin/users"),
    assignRole: (cuid, role) => request("/admin/users", { method: "POST", body: { cuid, role } }),
    setRole: (uid, role) => request(`/admin/users/${id(uid)}`, { method: "PUT", body: { role } }),
    setStatus: (uid, is_active) => request(`/admin/users/${id(uid)}/status`, { method: "POST", body: { is_active } }),
    referentiels: () => request("/admin/referentiels"),
    addRef: (kind, libelle, manager_cuid, direction_id, direction_libelle) =>
      request(`/admin/referentiels/${id(kind)}`, {
        method: "POST",
        body: {
          libelle,
          manager_cuid: manager_cuid || null,
          direction_id: direction_id || null,
          direction_libelle: direction_libelle || null,
        },
      }),
    renameRef: (kind, rid, libelle, manager_cuid, direction_id, direction_libelle) =>
      request(`/admin/referentiels/${id(kind)}/${id(rid)}`, {
        method: "PUT",
        body: {
          libelle,
          manager_cuid: manager_cuid || null,
          direction_id: direction_id || null,
          direction_libelle: direction_libelle || null,
        },
      }),
    deleteRef: (kind, rid) => request(`/admin/referentiels/${id(kind)}/${id(rid)}`, { method: "DELETE" }),
    audit: (params) => request(`/admin/audit?${query(params)}`),
  },
};
