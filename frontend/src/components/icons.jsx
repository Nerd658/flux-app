// Icônes SVG inline (aucune dépendance externe, compatibles CSP stricte)
const base = {
  width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, focusable: "false",
};

const make = (paths) => (props) => <svg {...base} {...props}>{paths}</svg>;

export const IconPlus = make(<path d="M12 5v14M5 12h14" />);
export const IconList = make(<><path d="M9 6h12M9 12h12M9 18h12" /><path d="M4 6h.01M4 12h.01M4 18h.01" /></>);
export const IconShield = make(<><path d="M12 3 4.5 6v6c0 4.6 3.1 8 7.5 9 4.4-1 7.5-4.4 7.5-9V6L12 3Z" /><path d="m9 12 2 2 4-4" /></>);
export const IconLogout = make(<><path d="M15 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3" /><path d="m10 17-5-5 5-5" /><path d="M5 12h11" /></>);
export const IconLock = make(<><rect x="4.5" y="11" width="15" height="10" rx="2.5" /><path d="M8 11V7.5a4 4 0 0 1 8 0V11" /></>);
export const IconUser = make(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);
export const IconEye = make(<><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>);
export const IconEyeOff = make(<><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-2.2 3.1M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7c1.7 0 3.2-.4 4.5-1.1" /><path d="m2 2 20 20M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>);
export const IconTrash = make(<><path d="M4 7h16M9 7V4.5h6V7M6.5 7l.9 12.2a2 2 0 0 0 2 1.8h5.2a2 2 0 0 0 2-1.8L17.5 7" /></>);
export const IconCopy = make(<><rect x="9" y="9" width="12" height="12" rx="2.5" /><path d="M5 15h-.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" /></>);
export const IconCheck = make(<path d="m5 12.5 4.5 4.5L19 7.5" />);
export const IconX = make(<path d="M18 6 6 18M6 6l12 12" />);
export const IconChevronLeft = make(<path d="m15 18-6-6 6-6" />);
export const IconChevronRight = make(<path d="m9 18 6-6-6-6" />);
export const IconChevronDown = make(<path d="m6 9 6 6 6-6" />);
export const IconArrowLeft = make(<path d="M19 12H5m6 7-7-7 7-7" />);
export const IconArrowRight = make(<path d="M5 12h14m-6-7 7 7-7 7" />);
export const IconDownload = make(<><path d="M12 3v12m-5-5 5 5 5-5" /><path d="M4 21h16" /></>);
export const IconCalendar = make(<><rect x="3.5" y="5" width="17" height="16" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>);
export const IconSearch = make(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>);
export const IconServers = make(<><rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.5h.01M7 16.5h.01" /></>);
export const IconGlobe = make(<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>);
export const IconTag = make(<><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z" /><path d="M7.5 7.5h.01" /></>);
export const IconInbox = make(<><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6L5.5 5Z" /></>);
export const IconAlert = make(<><circle cx="12" cy="12" r="9" /><path d="M12 8v4.5m0 3.5h.01" /></>);
export const IconInfo = make(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5.5M12 7.5h.01" /></>);
export const IconFingerprint = make(<><path d="M12 11v3a8 8 0 0 1-1.5 4.7" /><path d="M8 12a4 4 0 0 1 8 0v1a12 12 0 0 1-.9 4.6" /><path d="M5 15.5A10 10 0 0 1 4.6 12 7.4 7.4 0 0 1 19.4 12c0 .8 0 1.6-.1 2.4" /></>);
export const IconFlow = make(<><circle cx="5" cy="12" r="2.5" /><circle cx="19" cy="12" r="2.5" /><path d="M7.5 12h9m-3-3 3 3-3 3" /></>);
export const IconGrid = make(<><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" /><rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></>);
export const IconUsers = make(<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.3a6.5 6.5 0 0 1 3.5 5.7" /></>);
export const IconLayers = make(<><path d="m12 3 9 4.5-9 4.5-9-4.5L12 3Z" /><path d="m3 12 9 4.5 9-4.5" /><path d="m3 16.5 9 4.5 9-4.5" /></>);
export const IconHistory = make(<><path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5" /><path d="M3.5 3.5v5h5" /><path d="M12 7.5V12l3 2" /></>);
export const IconPencil = make(<><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></>);
export const IconKey = make(<><circle cx="8" cy="15" r="4" /><path d="m10.8 12.2 8.7-8.7M17 6l3 3M14.5 8.5l2 2" /></>);
export const IconPower = make(<><path d="M12 3v8" /><path d="M6.3 6.8a8 8 0 1 0 11.4 0" /></>);
export const IconUserPlus = make(<><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0" /><path d="M19 8v6M16 11h6" /></>);
export const IconClock = make(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>);
export const IconFileCheck = make(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5" /><path d="m9 14.5 2 2 4-4" /></>);
export const IconGauge = make(<><path d="M12 14 15.5 9.5" /><path d="M3.5 18a9 9 0 1 1 17 0" /><circle cx="12" cy="14" r="1.5" /></>);

// Logo de l'application : pastille orange, tracé « flux » en noir
export const BrandMark = () => (
  <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="5" cy="12" r="2.2" />
    <circle cx="19" cy="12" r="2.2" />
    <path d="M7.5 12h9m-3-3 3 3-3 3" fill="none" />
  </svg>
);
