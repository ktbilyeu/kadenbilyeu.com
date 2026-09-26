// Copyright 2024 Kaden Bilyeu (Bikatr7) (https://github.com/Bikatr7) (https://github.com/Bikatr7/kadenbilyeu.com) (https://kadenbilyeu.com)
// Use of this source code is governed by an GNU Affero General Public License v3.0
// license that can be found in the LICENSE file.

// react
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

// utils
import { authenticatedFetch, getURL } from '../utils';

interface SiteSettings {
    minimal_mode: boolean;
}

interface SiteSettingsContextType {
    settings: SiteSettings;
    isLoading: boolean;
    refreshSettings: () => Promise<void>;
    updateMinimalMode: (minimalMode: boolean) => Promise<void>;
}

// This fallback does not change the saved admin setting.
const redactedSettings: SiteSettings = {
    minimal_mode: true,
};

function validateSettings(value: unknown): SiteSettings {
    if (
        !value ||
        typeof value !== 'object' ||
        typeof (value as SiteSettings).minimal_mode !== 'boolean'
    ) {
        throw new Error('Invalid site settings response');
    }
    return { minimal_mode: (value as SiteSettings).minimal_mode };
}

const SiteSettingsContext = createContext<SiteSettingsContextType | undefined>(undefined);

export function SiteSettingsProvider({ children }: { children: React.ReactNode }) {
    const [settings, setSettings] = useState<SiteSettings>(redactedSettings);
    const [isLoading, setIsLoading] = useState(true);
    const readController = useRef<AbortController | null>(null);
    // Ignore responses from reads superseded by a newer read or admin update.
    const requestVersion = useRef(0);
    const updating = useRef(false);

    const refreshSettings = useCallback(async () => {
        if (updating.current) return;
        readController.current?.abort();
        const controller = new AbortController();
        readController.current = controller;
        const version = ++requestVersion.current;
        const timeout = window.setTimeout(() => controller.abort(), 8000);
        try {
            const response = await fetch(getURL('/site-settings'), {
                credentials: 'include',
                cache: 'no-store',
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error('Site settings are unavailable');
            }
            const nextSettings = validateSettings(await response.json());
            if (version === requestVersion.current) setSettings(nextSettings);
        } catch (error) {
            if (version === requestVersion.current) {
                setSettings(redactedSettings);
                console.error('Site settings unavailable; using redacted view:', error);
            }
        } finally {
            window.clearTimeout(timeout);
            if (version === requestVersion.current) setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        refreshSettings();
        const handleOffline = () => {
            ++requestVersion.current;
            readController.current?.abort();
            setSettings(redactedSettings);
            setIsLoading(false);
        };
        window.addEventListener('offline', handleOffline);
        window.addEventListener('online', refreshSettings);
        const interval = window.setInterval(refreshSettings, 30000);
        return () => {
            ++requestVersion.current;
            readController.current?.abort();
            window.clearInterval(interval);
            window.removeEventListener('offline', handleOffline);
            window.removeEventListener('online', refreshSettings);
        };
    }, [refreshSettings]);

    const updateMinimalMode = async (minimalMode: boolean) => {
        updating.current = true;
        readController.current?.abort();
        const version = ++requestVersion.current;
        try {
            const response = await authenticatedFetch(getURL('/site-settings'), {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    minimal_mode: minimalMode,
                }),
            });
            if (!response.ok) throw new Error('Failed to update site settings');
            const nextSettings = validateSettings(await response.json());
            if (version === requestVersion.current) setSettings(nextSettings);
        } catch (error) {
            if (version === requestVersion.current) setSettings(redactedSettings);
            throw error;
        } finally {
            updating.current = false;
            if (version === requestVersion.current) setIsLoading(false);
        }
    };

    return (
        <SiteSettingsContext.Provider value={{ settings, isLoading, refreshSettings, updateMinimalMode }}>
            {children}
        </SiteSettingsContext.Provider>
    );
}

export function useSiteSettings() {
    const context = useContext(SiteSettingsContext);

    if (context === undefined) {
        throw new Error('useSiteSettings must be used within a SiteSettingsProvider');
    }

    return context;
}
