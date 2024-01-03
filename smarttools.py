def normalize(smart):
    '''Load different types of SMART outputs'''

    ret = dict()
    ret.update({ "temperature"      : 0 })
    ret.update({ "critical_warning" : 0 })
    ret.update({ "unsafe_shutdowns" : 0 })
    ret.update({ "power_cycles"     : 0 })
    ret.update({ "power_on_hours"   : 0 })
    ret.update({ "available_spare"  : 100 })
    ret.update({ "wearleveling_count" : 100 })

    if "ata_smart_attributes" in smart:

        # get main table #
        table = smart["ata_smart_attributes"]["table"]
        
        # temperatur #
        ret["temperature"] = smart["temperature"]["current"]

        for el in table:
        
            # look for relevant metrics #
            name = el["name"].lower()
            target_name = el["name"].lower() # name in return map

            # handle value mapping #
            use_raw = False
            if name == "used_rsvd_blk_cnt_tot":
                target_name = "available_spare"
            elif name == "power_cylce_count":
                target_name = "power_cycles"
                use_raw = True
            elif name == "power_on_hours":
                target_name = "power_on_hours"
                use_raw = True

            # check if metric should be recorded #
            if target_name in ret:

                # set return dict #
                if use_raw:
                    value = el["raw"]["value"]
                else:
                    value = el["value"]

                ret[target_name] = value

    return ret
