# JUPI: retain only the loader-provided console HDD key before switch_root.
# The existing USB root selector above this hook remains unchanged.
if [ -f /key/eap_hdd_key.bin ] && [ "$(wc -c < /key/eap_hdd_key.bin)" -eq 32 ]; then
    (
        umask 077
        D=/newroot/var/backups/jupi/device-secrets
        if [ ! -L /newroot/var/backups ] && [ ! -L /newroot/var/backups/jupi ] && [ ! -L "$D" ]; then
            if mkdir -p "$D" && chmod 700 /newroot/var/backups/jupi "$D"; then
                if [ ! -e "$D/eap_hdd_key.bin" ] && [ ! -L "$D/eap_hdd_key.bin" ]; then
                    T="$D/.key-capture-$$"
                    if cp /key/eap_hdd_key.bin "$T" && chmod 600 "$T" && cmp -s /key/eap_hdd_key.bin "$T"; then
                        mv "$T" "$D/eap_hdd_key.bin" && sync && echo JUPI_CONSOLE_KEY_RETAINED
                    else
                        rm -f "$T"
                        echo JUPI_CONSOLE_KEY_CAPTURE_FAILED
                    fi
                elif cmp -s /key/eap_hdd_key.bin "$D/eap_hdd_key.bin"; then
                    echo JUPI_CONSOLE_KEY_ALREADY_RETAINED
                else
                    echo JUPI_CONSOLE_KEY_DIFFERENT_EXISTING_FILE_PRESERVED
                fi
            fi
        fi
    )
else
    echo JUPI_NO_LOADER_CONSOLE_KEY
fi
