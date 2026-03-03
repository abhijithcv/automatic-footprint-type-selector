import pcbnew
import wx

class MixedPadDialog(wx.Dialog):
    def __init__(self, mixed_refs):
        super().__init__(None, title="Mixed Pads Detected", size=(400, 350))
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        lbl = f"Found {len(mixed_refs)} footprints with both SMD and PTH pads:"
        vbox.Add(wx.StaticText(panel, label=lbl), 0, wx.ALL, 10)

        self.listbox = wx.ListBox(panel, choices=mixed_refs, size=(-1, 80))
        vbox.Add(self.listbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 15)

        vbox.Add(wx.StaticText(panel, label="How should these be handled?"), 0, wx.ALL, 10)

        self.opt_unspecified = wx.RadioButton(panel, label="Set to Unspecified (Recommended)", style=wx.RB_GROUP)
        self.opt_smd = wx.RadioButton(panel, label="Set all to SMD")
        self.opt_tht = wx.RadioButton(panel, label="Set all to Through hole")
        self.opt_keep = wx.RadioButton(panel, label="Keep existing configuration")

        self.opt_unspecified.SetValue(True)

        for opt in [self.opt_unspecified, self.opt_smd, self.opt_tht, self.opt_keep]:
            vbox.Add(opt, 0, wx.LEFT | wx.BOTTOM, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, label="Apply")
        btn_sizer.Add(ok_btn, 0, wx.ALL, 10)
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER)

        panel.SetSizer(vbox)

    def GetChoice(self):
        if self.opt_smd.GetValue(): return "smd"
        if self.opt_tht.GetValue(): return "tht"
        if self.opt_keep.GetValue(): return "keep"
        return "unspecified"

class FootprintTypeFixer(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Footprint Type Fixer"
        self.category = "Maintenance"
        self.description = "Fixes SMD/THT attributes while ignoring mechanical holes"
        self.show_toolbar_button = True

    def Run(self):
        board = pcbnew.GetBoard()
        fps = board.GetFootprints()

        # Handle KiCad version differences for Attributes
        try:
            FP_SMD = pcbnew.FP_SMD
            FP_THT = pcbnew.FP_THROUGH_HOLE
        except AttributeError:
            FP_SMD = 1
            FP_THT = 0

        # Identify truly mixed footprints
        mixed_fps = []
        for fp in fps:
            pads = fp.Pads()
            has_smd = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in pads)
            # Only count Plated Through Holes as "THT" for classification
            has_pth = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in pads)
            
            if has_smd and has_pth:
                mixed_fps.append(fp)

        mixed_action = "unspecified"
        if mixed_fps:
            refs = [fp.GetReference() for fp in mixed_fps]
            dlg = MixedPadDialog(refs)
            if dlg.ShowModal() == wx.ID_OK:
                mixed_action = dlg.GetChoice()
            dlg.Destroy()

        counts = {"smd": 0, "tht": 0, "unspecified": 0, "no_change": 0}

        for fp in fps:
            pads = fp.Pads()
            has_smd = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in pads)
            has_pth = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in pads)

            target = None

            if has_smd and has_pth:
                if mixed_action == "smd":
                    target = FP_SMD
                elif mixed_action == "tht":
                    target = FP_THT
                elif mixed_action == "keep":
                    target = None # Do nothing
                else:
                    target = "unspecified"
            
            elif has_smd and not has_pth:
                # Catch SMD footprints with mechanical holes
                target = FP_SMD
            
            elif has_pth and not has_smd:
                target = FP_THT
            
            else:
                # If only mechanical holes or empty, default to unspecified
                target = "unspecified"

            if target is not None:
                current_attr = fp.GetAttributes()

                if target == "unspecified":
                    # Clear both SMD and THT bits
                    new_attr = current_attr & ~(FP_SMD | FP_THT)
                    if current_attr != new_attr:
                        fp.SetAttributes(new_attr)
                        counts["unspecified"] += 1
                    else:
                        counts["no_change"] += 1
                elif current_attr != target:
                    fp.SetAttributes(target)
                    if target == FP_SMD:
                        counts["smd"] += 1
                    elif target == FP_THT:
                        counts["tht"] += 1
                else:
                    counts["no_change"] += 1
            else:
                counts["no_change"] += 1

        pcbnew.Refresh()

        msg = (f"Processing Finished:\n\n"
               f"• {counts['smd']} changed to SMD\n"
               f"• {counts['tht']} changed to Through hole\n"
               f"• {counts['unspecified']} changed to Unspecified\n"
               f"• {counts['no_change']} footprints were already correct or skipped.")
        wx.MessageBox(msg, "Results", wx.OK | wx.ICON_INFORMATION)

FootprintTypeFixer().register()