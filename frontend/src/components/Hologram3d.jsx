import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  useAnimations,
  useGLTF,
  Float,
  Sparkles,
  OrbitControls,
} from "@react-three/drei";
import * as THREE from "three";
import "./avatar.css";

const COLOR_MAP = {
  cyan: "#67e8f9",
  pink: "#f9a8d4",
  purple: "#c4b5fd",
  green: "#86efac",
  gold: "#fcd34d",
};

function getAvatarColor(hologramColor) {
  return COLOR_MAP[hologramColor] || COLOR_MAP.cyan;
}

function getAccessoryColor(hologramColor) {
  if (hologramColor === "gold") return "#fff1a6";
  if (hologramColor === "pink") return "#ffd1e8";
  if (hologramColor === "purple") return "#e9ddff";
  if (hologramColor === "green") return "#d9ffe7";
  return "#d9fbff";
}

function pickClipName(names, preferred) {
  if (!names?.length) return null;

  const lowered = names.map((name) => name.toLowerCase());

  for (const target of preferred) {
    const index = lowered.findIndex((name) => name.includes(target));
    if (index !== -1) return names[index];
  }

  return names[0] || null;
}

function FallbackHumanoid({ hologramColor = "cyan", accessory = "none" }) {
  const color = getAvatarColor(hologramColor);
  const accessoryColor = getAccessoryColor(hologramColor);
  const groupRef = useRef(null);

  useFrame((state) => {
    if (!groupRef.current) return;

    const t = state.clock.elapsedTime;
    groupRef.current.position.y = Math.sin(t * 1.5) * 0.05;
    groupRef.current.rotation.y = Math.sin(t * 0.55) * 0.08;
    groupRef.current.rotation.z = Math.sin(t * 0.9) * 0.015;
  });

  return (
    <group ref={groupRef} position={[0, -0.45, 0]}>
      <mesh position={[0, 1.55, 0]}>
        <sphereGeometry args={[0.24, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.65}
          transparent
          opacity={0.92}
        />
      </mesh>

      <mesh position={[0, 0.95, 0]}>
        <capsuleGeometry args={[0.26, 0.95, 8, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.45}
          transparent
          opacity={0.84}
        />
      </mesh>

      <mesh position={[-0.36, 0.95, 0]} rotation={[0, 0, 0.22]}>
        <capsuleGeometry args={[0.07, 0.7, 6, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.32}
          transparent
          opacity={0.8}
        />
      </mesh>

      <mesh position={[0.36, 0.95, 0]} rotation={[0, 0, -0.22]}>
        <capsuleGeometry args={[0.07, 0.7, 6, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.32}
          transparent
          opacity={0.8}
        />
      </mesh>

      <mesh position={[-0.15, 0.1, 0]}>
        <capsuleGeometry args={[0.08, 0.8, 6, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.32}
          transparent
          opacity={0.8}
        />
      </mesh>

      <mesh position={[0.15, 0.1, 0]}>
        <capsuleGeometry args={[0.08, 0.8, 6, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.32}
          transparent
          opacity={0.8}
        />
      </mesh>

      {accessory === "bow" && (
        <mesh position={[0, 1.82, 0.08]} scale={[0.22, 0.12, 0.08]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial
            color={accessoryColor}
            emissive={accessoryColor}
            emissiveIntensity={0.7}
            transparent
            opacity={0.95}
          />
        </mesh>
      )}
    </group>
  );
}

function GLBHumanoid({
  state = "idle",
  avatarType = "female",
  hologramColor = "cyan",
  accessory = "none",
}) {
  const wrapperRef = useRef(null);
  const modelRootRef = useRef(null);
  const [activeAction, setActiveAction] = useState(null);

  const color = getAvatarColor(hologramColor);
  const accessoryColor = getAccessoryColor(hologramColor);

  const modelPath =
    avatarType === "male"
      ? "/models/synk-male.glb"
      : avatarType === "cartoon"
        ? "/models/synk-cartoon.glb"
        : "/models/synk-female.glb";

  const gltf = useGLTF(modelPath);
  const { scene, animations } = gltf;
  const { actions, names } = useAnimations(animations, modelRootRef);

  const idleClip = useMemo(
    () => pickClipName(names, ["idle", "breath", "standing"]),
    [names]
  );

  const talkClip = useMemo(
    () => pickClipName(names, ["talk", "speaking", "gesture"]),
    [names]
  );

  const thinkClip = useMemo(
    () => pickClipName(names, ["think", "ponder"]),
    [names]
  );

  const listenClip = useMemo(
    () => pickClipName(names, ["listen", "attention"]),
    [names]
  );

  useEffect(() => {
    scene.traverse((object) => {
      if (!object.isMesh || !object.material) return;

      object.castShadow = true;
      object.receiveShadow = true;

      const clonedMaterial = Array.isArray(object.material)
        ? object.material.map((mat) => mat.clone())
        : object.material.clone();

      const applyMaterial = (mat) => {
        if (!mat) return;

        mat.color = new THREE.Color(color);

        if ("emissive" in mat) {
          mat.emissive = new THREE.Color(color);
          mat.emissiveIntensity = 0.32;
        }

        mat.transparent = true;
        mat.opacity = 0.92;
        mat.depthWrite = true;

        if ("roughness" in mat) mat.roughness = 0.28;
        if ("metalness" in mat) mat.metalness = 0.12;
      };

      if (Array.isArray(clonedMaterial)) clonedMaterial.forEach(applyMaterial);
      else applyMaterial(clonedMaterial);

      object.material = clonedMaterial;
    });
  }, [scene, color]);

  useEffect(() => {
    if (!wrapperRef.current) return;
    wrapperRef.current.position.set(0, -1.15, 0);
    wrapperRef.current.rotation.set(0, 0, 0);
  }, []);

  useEffect(() => {
    if (!actions || !names?.length) return;

    let nextClip = idleClip;

    if (state === "talking" && talkClip) nextClip = talkClip;
    else if (state === "thinking" && thinkClip) nextClip = thinkClip;
    else if (state === "listening" && listenClip) nextClip = listenClip;

    if (!nextClip || !actions[nextClip] || activeAction === nextClip) return;

    Object.values(actions).forEach((action) => action?.fadeOut(0.25));
    actions[nextClip].reset().fadeIn(0.25).play();
    setActiveAction(nextClip);
  }, [
    actions,
    names,
    activeAction,
    idleClip,
    talkClip,
    thinkClip,
    listenClip,
    state,
  ]);

  useFrame((stateObj, delta) => {
    if (!wrapperRef.current || !modelRootRef.current) return;

    const wrapper = wrapperRef.current;
    const model = modelRootRef.current;
    const t = stateObj.clock.elapsedTime;
    const hasAnimations = Array.isArray(animations) && animations.length > 0;

    wrapper.position.y = -1.15 + Math.sin(t * 1.4) * 0.05;

    if (!hasAnimations) {
      if (state === "talking") {
        model.rotation.y = Math.sin(t * 1.6) * 0.08;
        model.position.y = Math.sin(t * 3.0) * 0.02;
      } else if (state === "thinking") {
        model.rotation.y = Math.sin(t * 0.8) * 0.12;
        model.position.y = 0;
      } else if (state === "listening") {
        model.rotation.y = THREE.MathUtils.lerp(model.rotation.y, 0, 4 * delta);
        model.position.y = Math.sin(t * 2.2) * 0.01;
      } else {
        model.rotation.y = Math.sin(t * 0.5) * 0.03;
        model.rotation.z = Math.sin(t * 0.8) * 0.015;
        model.position.y = Math.sin(t * 1.1) * 0.01;
      }

      return;
    }

    if (state === "talking") {
      wrapper.rotation.y = Math.sin(t * 1.2) * 0.05;
    } else if (state === "thinking") {
      wrapper.rotation.y = Math.sin(t * 0.6) * 0.07;
    } else if (state === "listening") {
      wrapper.rotation.y = THREE.MathUtils.lerp(wrapper.rotation.y, 0, 3 * delta);
    } else {
      wrapper.rotation.y = Math.sin(t * 0.35) * 0.025;
    }
  });

  return (
    <group ref={wrapperRef}>
      <Float speed={0.85} rotationIntensity={0.02} floatIntensity={0.04}>
        <group
          ref={modelRootRef}
          scale={2.1}
          rotation={[0, Math.PI, 0]}
          position={[0, 0, 0]}
        >
          <primitive object={scene} />
        </group>
      </Float>

      {accessory === "bow" && (
        <mesh position={[0, 1.8, 0.08]} scale={[0.22, 0.12, 0.08]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial
            color={accessoryColor}
            emissive={accessoryColor}
            emissiveIntensity={0.7}
            transparent
            opacity={0.95}
          />
        </mesh>
      )}

      <Sparkles
        count={22}
        scale={[2.8, 2.8, 2.8]}
        size={1.7}
        speed={0.13}
        color={color}
      />
    </group>
  );
}

class ModelErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error("GLB avatar crashed:", error);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

function SafeAvatar(props) {
  const fallback = (
    <FallbackHumanoid
      hologramColor={props.hologramColor}
      accessory={props.accessory}
    />
  );

  return (
    <ModelErrorBoundary fallback={fallback}>
      <Suspense fallback={fallback}>
        <GLBHumanoid {...props} />
      </Suspense>
    </ModelErrorBoundary>
  );
}

function Platform({ hologramColor = "cyan" }) {
  const color = getAvatarColor(hologramColor);

  return (
    <group position={[0, -1.45, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <ringGeometry args={[2.08, 2.42, 64]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.58}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[1.35, 1.68, 64]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.42}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <circleGeometry args={[2.8, 64]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.035}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function EnergyColumn({ hologramColor = "cyan" }) {
  const color = getAvatarColor(hologramColor);

  return (
    <mesh position={[0, 0.25, 0]}>
      <cylinderGeometry args={[1.5, 1.9, 4.1, 48, 1, true]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.045}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

export default function Hologram3d({
  state = "idle",
  isExpanded = false,
  onToggleExpand = () => {},
  statusText = "SYNK Avatar",
  avatarType = "female",
  hologramColor = "cyan",
  accessory = "none",
}) {
  const [audioLevel, setAudioLevel] = useState(0);
  const animationFrameRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    if (state !== "listening") {
      setAudioLevel(0);
      return;
    }

    let audioContext;
    let analyser;
    let dataArray;

    async function setupMicGlow() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

        streamRef.current = stream;

        audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;

        source.connect(analyser);
        dataArray = new Uint8Array(analyser.frequencyBinCount);

        function updateAudioLevel() {
          analyser.getByteFrequencyData(dataArray);

          const avg =
            dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;

          const level = Math.min(avg / 255, 0.9);
          setAudioLevel((prev) => prev * 0.7 + level * 0.3);

          animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
        }

        updateAudioLevel();
      } catch (error) {
        console.error("Mic audio glow error:", error);
        setAudioLevel(0);
      }
    }

    setupMicGlow();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      streamRef.current?.getTracks().forEach((track) => track.stop());

      if (audioContext) {
        audioContext.close();
      }
    };
  }, [state]);

  return (
    <div
      className={`synk-avatar-shell ${isExpanded ? "expanded" : ""}`}
      onClick={onToggleExpand}
      title={statusText}
    >
      <div
        className={`synk-avatar ${state}`}
        style={{
          transform: `scale(${1 + audioLevel * 0.08})`,
          filter: `brightness(${1 + audioLevel * 0.6})`,
        }}
      >
        <Canvas
          shadows
          camera={{ position: [0, 1.2, 5.6], fov: 36 }}
          dpr={[1, 2]}
          gl={{
            alpha: true,
            antialias: true,
            preserveDrawingBuffer: false,
          }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
          }}
          style={{
            width: "100%",
            height: "100%",
            background: "transparent",
          }}
        >
          <ambientLight intensity={0.85} />

          <pointLight
            position={[0, 2, 3]}
            intensity={8}
            color={getAvatarColor(hologramColor)}
          />

          <pointLight position={[0, -1, 2]} intensity={4} color="#60a5fa" />

          <pointLight position={[3, 1.5, -2]} intensity={2.5} color="#ffffff" />

          <pointLight position={[0, 0, -5]} intensity={1.5} color="#0ea5e9" />

          <EnergyColumn hologramColor={hologramColor} />
          <Platform hologramColor={hologramColor} />

          <SafeAvatar
            state={state}
            avatarType={avatarType}
            hologramColor={hologramColor}
            accessory={accessory}
          />

          <OrbitControls
            enablePan={false}
            enableZoom={false}
            minPolarAngle={Math.PI / 2.6}
            maxPolarAngle={Math.PI / 1.95}
            minAzimuthAngle={-0.55}
            maxAzimuthAngle={0.55}
          />
        </Canvas>
      </div>
    </div>
  );
}

useGLTF.preload("/models/synk-female.glb");
useGLTF.preload("/models/synk-male.glb");
useGLTF.preload("/models/synk-cartoon.glb");