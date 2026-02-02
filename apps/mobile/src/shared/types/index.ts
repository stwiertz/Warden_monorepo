export interface Session {
  id: string;
  video_file_path: string;
  name: string | null;
  duration_ms: number | null;
  status: "importing" | "processing" | "ready" | "error";
  created_at: string;
  updated_at: string;
}

export interface MapSegment {
  id: string;
  session_id: string;
  map_index: number;
  start_time_ms: number;
  end_time_ms: number;
  map_name: string | null;
  result_frame_path: string | null;
  score_orange: number | null;
  score_blue: number | null;
  created_at: string;
}

export interface ClipExport {
  id: string;
  session_id: string;
  map_segment_id: string;
  start_time_ms: number;
  end_time_ms: number;
  view_mode: "pov" | "minimap";
  status: "defining" | "locked" | "exporting" | "ready" | "shared";
  export_quality: "mobile" | "hd" | null;
  file_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface AudioComment {
  id: string;
  clip_export_id: string;
  slot: "before" | "during" | "after";
  file_path: string;
  duration_ms: number;
  created_at: string;
}
