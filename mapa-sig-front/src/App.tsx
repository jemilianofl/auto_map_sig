import { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [incluirAutor, setIncluirAutor] = useState(true);
  const [autor, setAutor] = useState("Responsable Técnico ZOFEMAT");
  const [simbologia, setSimbologia] = useState<Record<string, { color: string, visible: boolean }>>({});
  const [mapaUrl, setMapaUrl] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    setFile(selectedFile);

    if (selectedFile) {
      const text = await selectedFile.text();
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(text, "text/xml");
      
      const placemarks = Array.from(xmlDoc.getElementsByTagName("Placemark"));
      const uniqueNames = new Set<string>();
      
      placemarks.forEach(p => {
        const nameNode = p.getElementsByTagName("name")[0];
        if (nameNode && nameNode.textContent) {
          uniqueNames.add(nameNode.textContent.trim());
        }
      });

      const coloresBase = ["#FF0000", "#1E90FF", "#32CD32", "#FFD700", "#8A2BE2"];
      const nuevaSimbologia: Record<string, { color: string, visible: boolean }> = {};
      
      Array.from(uniqueNames).forEach((nombre, index) => {
        nuevaSimbologia[nombre] = {
          color: coloresBase[index % coloresBase.length],
          visible: true
        };
      });

      setSimbologia(nuevaSimbologia);
    } else {
      setSimbologia({});
    }
  };

  const handleColorChange = (nombre: string, color: string) => {
    setSimbologia(prev => ({ ...prev, [nombre]: { ...prev[nombre], color } }));
  };

  const toggleVisible = (nombre: string) => {
    setSimbologia(prev => ({ ...prev, [nombre]: { ...prev[nombre], visible: !prev[nombre].visible } }));
  };

  const generarMapa = async () => {
    if (!file) return alert("Por favor selecciona un archivo KML");
    
    const configAEnviar: Record<string, string> = {};
    Object.entries(simbologia).forEach(([nombre, config]) => {
      if (config.visible) {
        configAEnviar[nombre] = config.color;
      }
    });

    if (Object.keys(configAEnviar).length === 0) {
      return alert("Debes seleccionar al menos una capa para generar el mapa.");
    }
    
    setCargando(true);
    const formData = new FormData();
    formData.append("archivo", file);
    formData.append("autor", incluirAutor ? autor : "");
    formData.append("simbologia", JSON.stringify(configAEnviar));

    // Usar la variable de entorno (si no existe, usa localhost por seguridad)
    const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

    try {
      const response = await axios.post(`${apiUrl}/generar-mapa/`, formData, {
        responseType: 'blob'
      });
      const url = URL.createObjectURL(response.data);
      setMapaUrl(url);
    } catch (error) {
      console.error("Error generando el mapa", error);
      alert("Hubo un error al generar el mapa. Revisa la consola del backend.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', fontFamily: 'sans-serif', margin: 0 }}>
      <div style={{ width: '350px', padding: '20px', background: '#f5f5f5', overflowY: 'auto', flexShrink: 0, boxShadow: '2px 0 5px rgba(0,0,0,0.1)', zIndex: 10 }}>
        <h2 style={{ fontSize: '1.2rem', color: '#333' }}>Configuración del Mapa</h2>
        
        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '0.9rem', color: '#555' }}><strong>Archivo KML:</strong></label><br/>
          <input type="file" accept=".kml" onChange={handleFileChange} style={{ marginTop: '8px', fontSize: '0.85rem' }} />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <input 
              type="checkbox" 
              checked={incluirAutor} 
              onChange={e => setIncluirAutor(e.target.checked)} 
              id="chk-autor"
            />
            <label htmlFor="chk-autor" style={{ fontSize: '0.9rem', color: '#555', fontWeight: 'bold', cursor: 'pointer' }}>
              Incluir Autor
            </label>
          </div>
          {incluirAutor && (
            <input 
              type="text" 
              value={autor} 
              onChange={e => setAutor(e.target.value)} 
              style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
            />
          )}
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '0.9rem', color: '#555' }}><strong>Capas y Simbología:</strong></label>
          {Object.keys(simbologia).length === 0 && <p style={{fontSize: '12px', color: '#888'}}>Sube un KML para detectar capas</p>}
          
          {Object.entries(simbologia).map(([nombre, config]) => (
            <div key={nombre} style={{ display: 'flex', alignItems: 'center', marginTop: '12px', gap: '8px' }}>
              <input 
                type="checkbox" 
                checked={config.visible} 
                onChange={() => toggleVisible(nombre)} 
                title="Mostrar/Ocultar capa"
              />
              <input 
                type="color" 
                value={config.color} 
                onChange={e => handleColorChange(nombre, e.target.value)} 
                disabled={!config.visible}
                style={{ opacity: config.visible ? 1 : 0.4, cursor: config.visible ? 'pointer' : 'not-allowed' }}
              />
              <span style={{ fontSize: '11px', color: config.visible ? '#333' : '#999', lineHeight: '1.2' }}>
                {nombre}
              </span>
            </div>
          ))}
        </div>

        <button 
          onClick={generarMapa} 
          disabled={cargando || !file}
          style={{ width: '100%', padding: '12px', background: '#A01F41', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: cargando || !file ? 'not-allowed' : 'pointer', opacity: cargando || !file ? 0.7 : 1 }}
        >
          {cargando ? 'Procesando mapa...' : 'Actualizar Previsualización'}
        </button>
      </div>

      <div style={{ flexGrow: 1, padding: '20px', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#2c2c2c' }}>
        {mapaUrl ? (
          <img 
            src={mapaUrl} 
            alt="Mapa Generado" 
            style={{ 
              width: '100%', 
              height: '100%', 
              objectFit: 'contain',
              boxShadow: '0 8px 16px rgba(0,0,0,0.3)',
              backgroundColor: 'white'
            }} 
          />
        ) : (
          <div style={{ color: '#888', textAlign: 'center' }}>
            <p style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Visor Cartográfico</p>
            <p style={{ fontSize: '0.9rem' }}>Sube tu KML y haz clic en "Actualizar Previsualización"</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;