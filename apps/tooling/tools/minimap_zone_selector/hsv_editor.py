"""HSV editor panel for editing zone color parameters."""

import tkinter as tk

from .zone_model import Zone


class HSVEditor(tk.LabelFrame):
    """Inline editor for a zone's HSV center/tolerance, min_ratio, and weight.

    Args:
        parent: Parent tkinter widget.
        on_change: Callback invoked with the updated Zone after a valid Apply.
    """

    def __init__(self, parent, on_change):
        super().__init__(parent, text="HSV Editor", padx=6, pady=6)
        self._on_change = on_change
        self._zone = None

        # H center/tol, S center/tol, V center/tol
        self._vars = {}
        row = 0
        for label, key_c, key_t, range_hint in [
            ("H", "h_center", "h_tol", "0\u2013360"),
            ("S", "s_center", "s_tol", "0\u2013100"),
            ("V", "v_center", "v_tol", "0\u2013100"),
        ]:
            tk.Label(self, text=label).grid(row=row, column=0, sticky="e", padx=2)
            cv = tk.StringVar()
            self._vars[key_c] = cv
            tk.Entry(self, textvariable=cv, width=5).grid(row=row, column=1, padx=1)

            tk.Label(self, text="\u00b1").grid(row=row, column=2)
            tv = tk.StringVar()
            self._vars[key_t] = tv
            tk.Entry(self, textvariable=tv, width=5).grid(row=row, column=3, padx=1)

            tk.Label(self, text=f"({range_hint})", fg="gray").grid(
                row=row, column=4, sticky="w", padx=2
            )
            row += 1

        # min_ratio
        tk.Label(self, text="min_ratio").grid(row=row, column=0, sticky="e", padx=2)
        self._min_ratio_var = tk.StringVar()
        tk.Entry(self, textvariable=self._min_ratio_var, width=6).grid(
            row=row, column=1, padx=1
        )
        tk.Label(self, text="(0.0\u20131.0)", fg="gray").grid(
            row=row, column=2, columnspan=3, sticky="w", padx=2
        )
        row += 1

        # Weight display
        tk.Label(self, text="weight").grid(row=row, column=0, sticky="e", padx=2)
        self._weight_label = tk.Label(self, text="\u2014")
        self._weight_label.grid(row=row, column=1, columnspan=2, sticky="w", padx=2)
        self._manual_label = tk.Label(self, text="", fg="orange")
        self._manual_label.grid(row=row, column=3, columnspan=2, sticky="w")
        row += 1

        # Error label
        self._error_label = tk.Label(self, text="", fg="red")
        self._error_label.grid(row=row, column=0, columnspan=5, sticky="w", pady=(2, 0))
        row += 1

        # Apply button
        tk.Button(self, text="Apply", command=self._apply).grid(
            row=row, column=0, columnspan=5, pady=(4, 0)
        )

    def load_zone(self, zone: Zone):
        """Populate fields from a Zone."""
        self._zone = zone
        self._vars["h_center"].set(str(zone.h_center))
        self._vars["h_tol"].set(str(zone.h_tol))
        self._vars["s_center"].set(str(zone.s_center))
        self._vars["s_tol"].set(str(zone.s_tol))
        self._vars["v_center"].set(str(zone.v_center))
        self._vars["v_tol"].set(str(zone.v_tol))
        self._min_ratio_var.set(str(zone.min_ratio))
        self._weight_label.config(text=f"{zone.weight:.4f}")
        self._manual_label.config(
            text="(manual)" if zone.weight_override else ""
        )
        self._error_label.config(text="")

    def _apply(self):
        if self._zone is None:
            return

        # Parse and validate
        try:
            h_c = int(self._vars["h_center"].get())
            h_t = int(self._vars["h_tol"].get())
            s_c = int(self._vars["s_center"].get())
            s_t = int(self._vars["s_tol"].get())
            v_c = int(self._vars["v_center"].get())
            v_t = int(self._vars["v_tol"].get())
        except ValueError:
            self._error_label.config(text="All HSV values must be integers")
            return

        try:
            min_ratio = float(self._min_ratio_var.get())
        except ValueError:
            self._error_label.config(text="min_ratio must be a number")
            return

        if not (0 <= h_c <= 360):
            self._error_label.config(text="H must be 0\u2013360")
            return
        if not (0 <= s_c <= 100):
            self._error_label.config(text="S must be 0\u2013100")
            return
        if not (0 <= v_c <= 100):
            self._error_label.config(text="V must be 0\u2013100")
            return
        if h_t < 0 or s_t < 0 or v_t < 0:
            self._error_label.config(text="Tolerances must be \u2265 0")
            return
        if not (0.0 <= min_ratio <= 1.0):
            self._error_label.config(text="min_ratio must be 0.0\u20131.0")
            return

        # Clear error, update zone
        self._error_label.config(text="")
        self._zone.h_center = h_c
        self._zone.h_tol = h_t
        self._zone.s_center = s_c
        self._zone.s_tol = s_t
        self._zone.v_center = v_c
        self._zone.v_tol = v_t
        self._zone.min_ratio = min_ratio

        self._on_change(self._zone)
