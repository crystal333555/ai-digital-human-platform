import React, { useRef, useEffect, useState, useMemo } from 'react'
import { Canvas, useFrame, useLoader } from '@react-three/fiber'
import { OrbitControls, useTexture } from '@react-three/drei'
import * as THREE from 'three'

// Error Boundary
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null } }
  static getDerivedStateFromError(error) { return { hasError: true, error } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, textAlign: 'center', color: '#ff4d4f' }}>
          <h3>3D 渲染失败</h3>
          <p>错误: {this.state.error?.message || 'Unknown'}</p>
        </div>
      )
    }
    return this.props.children
  }
}

function FaceMesh({ geometryData, imageUrl }) {
  const meshRef = useRef()
  
  const { texture, geometry } = useMemo(() => {
    if (!geometryData || !geometryData.data) return { texture: null, geometry: null }
    
    const geo = new THREE.BufferGeometry()
    const data = geometryData.data
    
    const positions = new Float32Array(data.attributes.position.array)
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    
    if (data.attributes.uv) {
      const uvs = new Float32Array(data.attributes.uv.array)
      geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2))
    }
    
    if (data.index) {
      const indices = new Uint16Array(data.index.array)
      geo.setIndex(new THREE.BufferAttribute(indices, 1))
    }
    
    geo.computeVertexNormals()
    
    let tex = null
    if (imageUrl) {
      const loader = new THREE.TextureLoader()
      tex = loader.load(imageUrl)
      tex.colorSpace = THREE.SRGBColorSpace
    }
    
    return { texture: tex, geometry: geo }
  }, [geometryData, imageUrl])
  
  if (!geometry) return null
  
  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial 
        map={texture} 
        side={THREE.DoubleSide}
        color={texture ? '#ffffff' : '#ff9999'}
      />
    </mesh>
  )
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} castShadow />
      <directionalLight position={[-5, 0, 5]} intensity={0.3} />
    </>
  )
}

function ThreeAvatarViewer({ avatar, meshData, imageUrl }) {
  const [error, setError] = useState(null)
  
  if (error) {
    return <div style={{ padding: 20, textAlign: 'center', color: '#ff4d4f' }}>3D渲染错误: {error.message}</div>
  }
  
  const resolvedImageUrl = imageUrl || (avatar?.original_image_path 
    ? `http://localhost:8000${avatar.original_image_path}` 
    : null)
  
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Canvas 
        shadows 
        camera={{ position: [0, 0, 2], fov: 50 }} 
        style={{ width: '100%', height: '100%' }}
        onError={(e) => setError(e)}
      >
        <ErrorBoundary>
          <Lights />
          <FaceMesh geometryData={meshData} imageUrl={imageUrl} />
          <OrbitControls
            enablePan={false}
            minDistance={1.5}
            maxDistance={4}
            minPolarAngle={Math.PI / 3}
            maxPolarAngle={Math.PI / 1.5}
          />
        </ErrorBoundary>
      </Canvas>
    </div>
  )
}

export default ThreeAvatarViewer
