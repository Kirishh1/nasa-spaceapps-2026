// Same-origin by default ("/api/..."); set NEXT_PUBLIC_API_URL only to point the UI at an API on another origin.
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export type Polygon = { type: "Polygon"; coordinates: number[][][] };

export interface StudyArea {
  id: string;
  name: string;
  description?: string;
  research_question?: string;
  featured_pair?: [string, string];
  bbox: [number, number, number, number];
  geometry: Polygon;
}

export interface Observation {
  id: string;
  sensor: string;
  band: string;
  product_type: string;
  product_version: string;
  date: string;
  start_time: string;
  end_time: string;
  track: number;
  frame: number;
  stack_id: string;
  pass_direction: string;
  polarizations: Record<string, string[]>;
  range_bandwidth_mhz: Record<string, string | null>;
  footprint: Polygon | null;
  size_bytes: number | null;
  browse_url: string | null;
  qa_report_url: string | null;
  ingested_layers: string[];
  available_for_analysis: boolean;
  unavailable_reason?: string;
}

export interface Issue {
  code: string;
  message: string;
}

export interface AnalysisConfig {
  frequency: "A" | "B";
  polarization: "HH" | "HV" | "VV" | "VH";
  threshold_db: number;
  speckle_filter: "lee" | "boxcar" | "none";
  filter_size: number;
  water_threshold_db: number;
  water_threshold_mode?: "otsu" | "fixed";
  min_region_m2: number;
  min_valid_fraction?: number;
  allow_cross_geometry?: boolean;
  include_precipitation?: boolean;
  include_reference?: boolean;
}

export interface AnalysisRequest {
  study_area_id: string;
  earlier_id: string;
  later_id: string;
  sensor: "NISAR" | "RCM" | "COMPARE";
  config: AnalysisConfig;
  geometry?: Polygon | null;
}

export interface ClassStat {
  pixels: number;
  area_km2: number;
  percent_of_valid: number;
}

export interface Distribution {
  mean?: number;
  std?: number;
  p05?: number;
  p25?: number;
  median?: number;
  p75?: number;
  p95?: number;
}

export interface Statistics {
  pixel_area_m2: number;
  analyzed_pixels: number;
  analyzed_area_km2: number;
  valid_pixels: number;
  valid_percent: number;
  missing_pixels: number;
  missing_area_km2: number;
  classes: { significant_decrease: ClassStat; significant_increase: ClassStat; limited_change: ClassStat };
  significant_change_area_km2: number;
  potential_inundation: { open_water: ClassStat; vegetated: ClassStat };
  delta_db: Distribution;
  noise_reference?: { robust_sigma_db: number; threshold_in_sigma: number; expected_exceedance_percent_gaussian: number; observed_exceedance_percent: number };
  earlier_db: Distribution;
  later_db: Distribution;
  histogram: { edges: number[]; counts: number[]; clipped_below: number; clipped_above: number };
}

export interface PrecipDay {
  date: string;
  mean_mm: number;
  max_mm: number;
  cells: number;
  product: string;
  run: string;
}

export interface Precipitation {
  status: "available" | "unavailable";
  reason?: string;
  source?: string;
  series?: PrecipDay[];
  missing_days?: string[];
  before_earlier_7d?: { days_requested: number; days_available: number; total_mm: number | null };
  before_later_7d?: { days_requested: number; days_available: number; total_mm: number | null };
  between_acquisitions?: { days_available: number; total_mm: number | null };
  caveat?: string;
}

export interface Metrics {
  pixels: number; tp: number; fp: number; fn: number; tn: number;
  precision: number | null; recall: number | null; f1: number | null; iou: number | null;
  overall_accuracy: number | null; kappa: number | null; predicted_fraction: number | null; reference_fraction: number | null;
}

export interface AccuracyEntry {
  side: "earlier" | "later"; nisar_date: string; product: "DSWX_S1" | "DSWX_HLS"; date: string; offset_days: number;
  track: string | null; observed_fraction: number; granules: string[]; open_water: Metrics; all_water: Metrics;
  threshold_sensitivity?: { threshold_db: number; f1: number | null; iou: number | null; precision: number | null; recall: number | null }[];
}

export interface WaterInfo {
  thresholds: Record<"earlier" | "later", { threshold_db: number; method: string }>;
  earlier_km2: number; later_km2: number; persistent_km2: number; gained_km2: number; lost_km2: number;
  earlier_fraction: number; later_fraction: number;
}

export interface SensorComparison {
  status: "available" | "unavailable"; reason?: string; sensor?: string; method?: string; cell_size_m?: number;
  earlier?: { date: string; track: number; granules: string[] }; later?: { date: string; track: number; granules: string[] };
  stats?: { compared_cells: number; counts: Record<string, number>; overall_agreement_percent: number | null; change_agreement_percent: number | null };
  by_landcover?: { class: number; name: string; cells: number; agree_percent: number; l_band_only_percent: number; c_band_only_percent: number; opposite_percent: number }[];
  cband_change_percent?: { decrease: number; increase: number };
}

export interface TimelinePoint { product: "DSWX_S1" | "DSWX_HLS"; date: string; observed_fraction: number; water_fraction: number | null; open_water_fraction: number | null }

export interface AnalysisResult {
  id: string;
  status: "complete";
  created_at: string;
  study_area: StudyArea;
  sensor: string;
  config: AnalysisConfig & Record<string, unknown>;
  earlier: Observation & Record<string, unknown>;
  later: Observation & Record<string, unknown>;
  days_between: number;
  grid: { crs: string; shape: [number, number]; pixel_spacing_m: [number, number]; bounds_lonlat: [number, number, number, number]; resampled: boolean };
  compatibility: { ok: boolean; errors: Issue[]; warnings: Issue[] };
  statistics: Statistics;
  inundation: Record<string, unknown> & { reason?: string; vegetated_flooding_reason?: string; min_region_pixels?: number };
  validation: {
    independently_validated: boolean;
    statement: string;
    jrc_surface_water?: Record<string, unknown> & {
      status?: string;
      reason?: string;
      open_water_candidates_evaluated?: number;
      fraction_candidates_in_historically_wet_pixels?: number | null;
      fraction_candidates_in_permanent_water?: number | null;
      baseline_fraction_historically_wet?: number | null;
      interpretation?: string;
      caveat?: string;
      source?: { name: string; citation: string; url: string };
    };
    landcover_breakdown?: {
      status?: string;
      reason?: string;
      source?: { name: string; citation: string; url: string };
      rows?: { class: number; name: string; pixels: number; percent_decrease: number; percent_increase: number }[];
    };
    errors?: string[];
    accuracy?: AccuracyEntry[];
    change_accuracy?: {
      product: "DSWX_S1" | "DSWX_HLS"; track: string | null; earlier_date: string; later_date: string; total_offset_days: number;
      water_lost: Metrics; water_gained: Metrics;
      cells_100m: { cells: number; pearson_r?: number | null; net_change_pred?: number; net_change_ref?: number; direction_agreement_where_changed?: number | null };
    }[];
    reference_change_self_agreement?: { pairs: number; f1_min: number; f1_max: number } | null;
    radiometric_stability?: { status: string; reason?: string; pixels?: number; median_delta_db?: number; iqr_db?: [number, number]; stable?: boolean; note?: string };
    swot?: {
      status: string; reason?: string; product?: string; note?: string;
      passes?: { pass: string; earlier_date: string; later_date: string; lakes: number; median_change_m: number; p25_m: number; p75_m: number; fraction_falling: number; median_uncertainty_m: number }[];
      area_agreement?: { status: string; lakes: number; outline_buffer_m?: number; earlier_area_r?: number | null; change_r?: number | null; change_spearman?: number | null;
        same_sign_fraction?: number; nisar_total_change_km2?: number; swot_total_change_km2?: number; nisar_earlier_total_km2?: number; swot_earlier_total_km2?: number };
    };
  };
  uncertainty: {
    pixel_spacing_m: number[];
    method: Record<string, string | number>;
    missing_data_percent: number;
    alignment: string[];
    compatibility_warnings: Issue[];
    false_positive_sources: string[];
    interpretation_caveat: string;
  };
  precipitation: Precipitation | null;
  sensor_comparison: SensorComparison;
  water?: WaterInfo;
  layers: string[];
}

export interface LegendItem {
  value: number;
  label: string;
  description?: string;
  color: string;
}

export interface MapLayer {
  id: string;
  title: string;
  kind: "continuous" | "categorical";
  tiles: string;
  bounds: [number, number, number, number];
  units?: string;
  rescale?: [number, number];
  colormap?: string;
  legend?: LegendItem[];
  description: string;
}

export interface DataResource {
  id: string;
  name: string;
  short_name?: string;
  identifier?: string;
  provider: string;
  role: string;
  status: "used" | "integrated" | "not_used";
  status_note?: string;
  links: { label: string; url: string }[];
}

export interface SourcesResponse {
  nasa: DataResource[];
  other: DataResource[];
  granules?: { id: string; date: string; download_url: string | null; qa_report_url: string | null; product_version: string }[];
}

export interface StoredAnalysis {
  id: string;
  created_at: string;
  study_area_id: string;
  earlier_id: string;
  later_id: string;
  earlier_date: string;
  later_date: string;
  subset: boolean;
  config: AnalysisConfig;
}

export interface JobStatus {
  id: string;
  status: "running" | "failed" | "complete";
  stage?: string;
  errors?: Issue[];
  warnings?: Issue[];
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public errors: Issue[] = [], public warnings: Issue[] = []) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError(`Cannot reach the SAR-Pulse API at ${API_BASE || "/api"}.`, 0);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(detail, res.status, body.errors ?? [], body.warnings ?? []);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string; study_areas: number; observations: number }>("/api/health"),
  studyAreas: () => request<StudyArea[]>("/api/study-areas"),
  observations: (studyArea: string, sensor = "NISAR") =>
    request<{ sensor: string; status: string; reason?: string; observations: Observation[] }>(
      `/api/observations?study_area=${encodeURIComponent(studyArea)}&sensor=${sensor}`,
    ),
  observation: (id: string) => request<Record<string, unknown>>(`/api/observations/${encodeURIComponent(id)}`),
  check: (req: AnalysisRequest) =>
    request<{ ok: boolean; errors: Issue[]; warnings: Issue[] }>("/api/analysis/check", { method: "POST", body: JSON.stringify(req) }),
  start: (req: AnalysisRequest) => request<{ id: string; status: string }>("/api/analysis", { method: "POST", body: JSON.stringify(req) }),
  sources: (analysisId?: string) => request<SourcesResponse>(`/api/sources${analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ""}`),
  rainfall: (studyArea: string) => request<{ status: string; series: { date: string; mean_mm: number }[] }>(`/api/study-areas/${encodeURIComponent(studyArea)}/rainfall`),
  timeline: (studyArea: string) => request<{ status: string; series: TimelinePoint[] }>(`/api/study-areas/${encodeURIComponent(studyArea)}/timeline`),
  analyses: (studyArea: string) => request<StoredAnalysis[]>(`/api/analyses?study_area=${encodeURIComponent(studyArea)}`),
  analysis: (id: string) => request<AnalysisResult | JobStatus>(`/api/analysis/${id}`),
  layers: (id: string) => request<{ id: string; layers: MapLayer[] }>(`/api/analysis/${id}/layers`),
  pixel: (id: string, lon: number, lat: number) =>
    request<{ lon: number; lat: number; values: Record<string, number | null> }>(`/api/analysis/${id}/pixel?lon=${lon}&lat=${lat}`),
};

export const tileUrl = (t: string) => `${API_BASE}${t}`;
