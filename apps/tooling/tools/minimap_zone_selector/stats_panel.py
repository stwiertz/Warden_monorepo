"""Stats panel — displays per-zone TP/FP/weight and per-map accuracy."""

import tkinter as tk

from tools.frame_labeler import MAP_LABELS

from .validator import ValidationResult
from .zone_model import MinimapConfig


class StatsPanel(tk.Frame):
    """Panel showing validation statistics for zones and maps.

    Args:
        parent: Parent tkinter widget.
        on_delete_zone: Callback(zone_id) when Delete is clicked.
        on_weight_override_change: Callback(zone_id, override: bool, manual_weight: float)
            when the Override checkbox or weight entry changes.
        on_select_zone: Callback(zone_id) when a zone row is clicked.
    """

    def __init__(self, parent, on_delete_zone, on_weight_override_change,
                 on_select_zone=None):
        super().__init__(parent)
        self._on_delete_zone = on_delete_zone
        self._on_weight_override_change = on_weight_override_change
        self._on_select_zone = on_select_zone

        # Overall accuracy
        self._overall_label = tk.Label(
            self, text="Overall: \u2014", font=("sans-serif", 11, "bold")
        )
        self._overall_label.pack(anchor="w", padx=4, pady=(4, 2))

        # Zone list section
        zone_header = tk.Label(
            self, text="Zones (selected map)", font=("sans-serif", 10, "bold")
        )
        zone_header.pack(anchor="w", padx=4, pady=(6, 2))

        self._zone_frame = tk.Frame(self)
        self._zone_frame.pack(fill="x", padx=4)

        # Map accuracy table section
        map_header = tk.Label(
            self, text="Map Accuracy", font=("sans-serif", 10, "bold")
        )
        map_header.pack(anchor="w", padx=4, pady=(10, 2))

        self._map_frame = tk.Frame(self)
        self._map_frame.pack(fill="x", padx=4)

    def refresh(self, result: ValidationResult, config: MinimapConfig,
                selected_map: str):
        """Rebuild zone list for selected_map and refresh the map accuracy table."""
        self._overall_label.config(
            text=f"Overall: {result.overall_accuracy * 100:.1f}%"
        )

        # --- Zone list ---
        for w in self._zone_frame.winfo_children():
            w.destroy()

        zones = config.maps.get(selected_map, [])
        if not zones:
            tk.Label(self._zone_frame, text="No zones", fg="gray").grid(
                row=0, column=0
            )
        else:
            # Header
            headers = ["Zone", "TP%", "FP%", "Weight", "Override", "Wt Val", ""]
            for ci, h in enumerate(headers):
                tk.Label(
                    self._zone_frame, text=h, font=("sans-serif", 9, "bold")
                ).grid(row=0, column=ci, padx=3, sticky="w")

            for ri, zone in enumerate(zones, start=1):
                zs = result.zone_stats.get(zone.zone_id)
                tp_str = f"{zs.tp_rate * 100:.1f}" if zs else "\u2014"
                fp_str = f"{zs.fp_rate * 100:.1f}" if zs else "\u2014"
                wt_str = f"{zone.weight:.3f}"

                # Zone id (clickable)
                zid_label = tk.Label(
                    self._zone_frame, text=zone.zone_id, fg="blue",
                    cursor="hand2"
                )
                zid_label.grid(row=ri, column=0, padx=3, sticky="w")
                zid_label.bind(
                    "<Button-1>",
                    lambda e, zid=zone.zone_id: (
                        self._on_select_zone(zid) if self._on_select_zone else None
                    ),
                )

                tk.Label(self._zone_frame, text=tp_str).grid(
                    row=ri, column=1, padx=3
                )
                tk.Label(self._zone_frame, text=fp_str).grid(
                    row=ri, column=2, padx=3
                )

                wt_label = tk.Label(self._zone_frame, text=wt_str)
                if zone.weight_override:
                    wt_label.config(fg="orange")
                wt_label.grid(row=ri, column=3, padx=3)

                # Override checkbox
                ov_var = tk.BooleanVar(value=zone.weight_override)
                ov_cb = tk.Checkbutton(self._zone_frame, variable=ov_var)
                ov_cb.grid(row=ri, column=4, padx=3)

                # Manual weight entry
                wt_entry_var = tk.StringVar(
                    value=f"{zone.weight:.3f}" if zone.weight_override else ""
                )
                wt_entry = tk.Entry(
                    self._zone_frame, textvariable=wt_entry_var, width=6,
                    state="normal" if zone.weight_override else "disabled",
                )
                wt_entry.grid(row=ri, column=5, padx=3)

                def _on_override_toggle(zid=zone.zone_id, var=ov_var,
                                        wvar=wt_entry_var, entry=wt_entry):
                    is_override = var.get()
                    entry.config(state="normal" if is_override else "disabled")
                    try:
                        manual_wt = float(wvar.get()) if is_override else 0.0
                    except ValueError:
                        manual_wt = 0.0
                    self._on_weight_override_change(zid, is_override, manual_wt)

                ov_cb.config(command=_on_override_toggle)

                # Bind entry Return for manual weight commit
                def _on_weight_entry(event, zid=zone.zone_id, wvar=wt_entry_var):
                    try:
                        manual_wt = float(wvar.get())
                    except ValueError:
                        return
                    self._on_weight_override_change(zid, True, manual_wt)

                wt_entry.bind("<Return>", _on_weight_entry)

                # Delete button
                tk.Button(
                    self._zone_frame,
                    text="Del",
                    fg="red",
                    command=lambda zid=zone.zone_id: self._on_delete_zone(zid),
                ).grid(row=ri, column=6, padx=3)

        # --- Map accuracy table ---
        for w in self._map_frame.winfo_children():
            w.destroy()

        map_headers = ["Map", "Acc%", "Cov Sim%"]
        for ci, h in enumerate(map_headers):
            tk.Label(
                self._map_frame, text=h, font=("sans-serif", 9, "bold")
            ).grid(row=0, column=ci, padx=4, sticky="w")

        row = 1
        for map_label in MAP_LABELS:
            ms = result.map_stats.get(map_label)
            if ms is None:
                continue

            acc_str = f"{ms.accuracy * 100:.1f}"
            zones_for_map = config.maps.get(map_label, [])
            if len(zones_for_map) <= 1:
                cov_str = "N/A"
            else:
                cov_str = f"{ms.coverage_sim_accuracy * 100:.1f}"

            fg = "red" if ms.accuracy < 1.0 else "black"

            tk.Label(self._map_frame, text=map_label, fg=fg).grid(
                row=row, column=0, padx=4, sticky="w"
            )
            tk.Label(self._map_frame, text=acc_str, fg=fg).grid(
                row=row, column=1, padx=4
            )
            tk.Label(self._map_frame, text=cov_str, fg=fg).grid(
                row=row, column=2, padx=4
            )
            row += 1
