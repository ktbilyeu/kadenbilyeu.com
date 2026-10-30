import React, { createContext, useContext, useState, useEffect } from 'react';

interface ThemeContextType {
    isRetro: boolean;
    toggleRetro: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children, forceStandardMode = false }: { children: React.ReactNode, forceStandardMode?: boolean }) {
    const [storedRetro, setStoredRetro] = useState<boolean>(() => {
        // Preserve the user's theme preference on every hostname.
        const savedRetro = localStorage.getItem('isRetro');
        return savedRetro ? JSON.parse(savedRetro) : false;
    });
    const isRetro = forceStandardMode ? false : storedRetro;

    useEffect(() => {
        localStorage.setItem('isRetro', JSON.stringify(storedRetro));
    }, [storedRetro]);

    const toggleRetro = () => {
        if (forceStandardMode) {
            return;
        }

        setStoredRetro(!storedRetro);
    };

    return (
        <ThemeContext.Provider value={{ isRetro, toggleRetro }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
} 
