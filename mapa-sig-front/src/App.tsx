import { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [autor, setAutor] = useState("Responsable Técnico ZOFEMAT");
  const [simbologia, setSimbologia] = useState<Record<string, string>>({});
  const [mapaUrl, setMapaUrl] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  // Leer el KML y extraer las capas dinámicamente
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
      const nuevaSimbologia: Record<string, string> = {};
      
      Array.from(uniqueNames).forEach((nombre, index) => {
        nuevaSimbologia[nombre] = coloresBase[index % coloresBase.length];
      });

      setSimbologia(nuevaSimbologia);
    } else {
      setSimbologia({});
    }
  };

  const handleColorChange = (nombre: string, color: string) => {
    setSimbologia(prev => ({ ...prev, [nombre]: color }));
  };

  const generarMapa = async () => {
    if (!file) return alert("Por favor selecciona un archivo KML");
    
    setCargando(true);
    const formData = new FormData();
    formData.append("archivo", file);
    formData.append("autor", autor);
    formData.append("simbologia", JSON.stringify(simbologia));

    try {
      const response = await axios.post("http://localhost:8000/generar-mapa/", formData, {
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
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
      <div style={{ width: '30%', padding: '20px', background: '#f5f5f5', overflowY: 'auto' }}>
        <h2>Configuración del Mapa</h2>
        
        <div style={{ marginBottom: '20px' }}>
          <label><strong>Archivo KML:</strong></label><br/>
          <input type="file" accept=".kml" onChange={handleFileChange} />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label><strong>Autor del Levantamiento:</strong></label><br/>
          <input 
            type="text" 
            value={autor} 
            onChange={e => setAutor(e.target.value)} 
            style={{ width: '100%', padding: '8px' }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label><strong>Simbología Detectada:</strong></label>
          {Object.keys(simbologia).length === 0 && <p style={{fontSize: '12px', color: '#666'}}>Sube un KML para ver las capas</p>}
          {Object.entries(simbologia).map(([nombre, color]) => (
            <div key={nombre} style={{ display: 'flex', alignItems: 'center', marginTop: '10px' }}>
              <input 
                type="color" 
                value={color} 
                onChange={e => handleColorChange(nombre, e.target.value)} 
                style={{ marginRight: '10px' }}
              />
              <span style={{ fontSize: '12px' }}>{nombre}</span>
            </div>
          ))}
        </div>

        <button 
          onClick={generarMapa} 
          disabled={cargando || !file}
          style={{ width: '100%', padding: '10px', background: '#A01F41', color: 'white', border: 'none', cursor: cargando || !file ? 'not-allowed' : 'pointer' }}
        >
          {cargando ? 'Generando...' : 'Actualizar Previsualización'}
        </button>
      </div>

      <div style={{ width: '70%', padding: '20px', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#e0e0e0' }}>
        {mapaUrl ? (
          <img src={mapaUrl} alt="Previsualización del Mapa" style={{ maxWidth: '100%', maxHeight: '100%', boxShadow: '0 4px 8px rgba(0,0,0,0.2)' }} />
        ) : (
          <p style={{ color: '#666' }}>El mapa generado aparecerá aquí.</p>
        )}
      </div>
    </div>
  );
}

export default App;