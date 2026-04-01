import React, { useState, useEffect, useCallback } from 'react';
import {
    StyleSheet, Text, View, TextInput, TouchableOpacity, Image, ScrollView,
    Alert, ActivityIndicator, FlatList, Modal, SafeAreaView, Dimensions, Linking
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { FontAwesome5, Ionicons, MaterialIcons } from '@expo/vector-icons';

// CONFIG: CHANGE TO YOUR BACKEND LAN IP
import Constants from 'expo-constants';
const debuggerHost = Constants.expoConfig?.hostUri || Constants.manifest?.debuggerHost || '';
const localIp = debuggerHost.split(':')[0] || '127.0.0.1';
const API_URL = `http://${localIp}:8000`;

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

export default function App() {
    const [token, setToken] = useState(null);
    const [userRole, setUserRole] = useState(null);
    const [loadingAuth, setLoadingAuth] = useState(true);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            setLoadingAuth(true);
            const t = await AsyncStorage.getItem('token');
            if (t) {
                // Fetch user data to determine role
                const res = await fetch(`${API_URL}/users/me`, {
                    headers: { 'Authorization': `Bearer ${t}` }
                });
                if (res.ok) {
                    const user = await res.json();
                    setUserRole(user.role);
                    setToken(t);
                } else {
                    await logout();
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingAuth(false);
        }
    };

    const login = async (t, role) => {
        await AsyncStorage.setItem('token', t);
        setUserRole(role);
        setToken(t);
    };

    const logout = async () => {
        await AsyncStorage.removeItem('token');
        setToken(null);
        setUserRole(null);
    };

    if (loadingAuth) {
        return (
            <View style={styles.centerContainer}>
                <ActivityIndicator size="large" color="#3b82f6" />
            </View>
        );
    }

    return (
        <NavigationContainer>
            {!token ? (
                <Stack.Navigator screenOptions={{ headerShown: false }}>
                    <Stack.Screen name="Login">
                        {(props) => <LoginScreen {...props} onLogin={login} />}
                    </Stack.Screen>
                    <Stack.Screen name="Register" component={RegisterScreen} />
                </Stack.Navigator>
            ) : (
                <MainTabs token={token} role={userRole} onLogout={logout} />
            )}
            <StatusBar style="light" />
        </NavigationContainer>
    );
}

// --- NAVIGATION TABS ---
function MainTabs({ token, role, onLogout }) {
    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                headerStyle: { backgroundColor: '#0f172a', borderBottomWidth: 1, borderBottomColor: '#1e293b' },
                headerTintColor: '#fff',
                tabBarStyle: { backgroundColor: '#0f172a', borderTopWidth: 1, borderTopColor: '#1e293b' },
                tabBarActiveTintColor: '#3b82f6',
                tabBarInactiveTintColor: '#64748b',
                tabBarIcon: ({ color, size }) => {
                    let iconName;
                    if (route.name === 'Analyze') iconName = 'microscope';
                    else if (route.name === 'History') iconName = 'clock-rotate-left';
                    else if (route.name === 'Doctors') iconName = 'user-md';
                    else if (route.name === 'Cases') iconName = 'folder-open';
                    else if (route.name === 'Notifications') iconName = 'bell';
                    else if (route.name === 'Profile') iconName = 'user-alt';
                    return <FontAwesome5 name={iconName} size={size - 4} color={color} />;
                },
            })}
        >
            {role === 'patient' && (
                <>
                    <Tab.Screen name="Analyze">
                        {() => <AnalyzeScreen token={token} />}
                    </Tab.Screen>
                    <Tab.Screen name="History">
                        {() => <HistoryScreen token={token} />}
                    </Tab.Screen>
                    <Tab.Screen name="Doctors">
                        {() => <DoctorsScreen token={token} />}
                    </Tab.Screen>
                </>
            )}

            {role === 'doctor' && (
                <>
                    <Tab.Screen name="Cases">
                        {() => <CasesScreen token={token} />}
                    </Tab.Screen>
                    <Tab.Screen name="History">
                        {() => <HistoryScreen token={token} />}
                    </Tab.Screen>
                </>
            )}

            <Tab.Screen name="Notifications">
                {() => <NotificationsScreen token={token} />}
            </Tab.Screen>
            <Tab.Screen name="Profile">
                {() => <ProfileScreen token={token} onLogout={onLogout} role={role} />}
            </Tab.Screen>
        </Tab.Navigator>
    );
}


// --- AUTH SCREENS ---

function LoginScreen({ navigation, onLogin }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const res = await fetch(`${API_URL}/auth/login`, { method: 'POST', body: formData });
            const data = await res.json();

            if (res.ok) {
                // Fetch user data to verify role
                const userRes = await fetch(`${API_URL}/users/me`, {
                    headers: { 'Authorization': `Bearer ${data.access_token}` }
                });
                const userData = await userRes.json();
                onLogin(data.access_token, userData.role);
            } else {
                Alert.alert("Error", data.detail || "Login failed");
            }
        } catch (e) {
            Alert.alert("Error", "Connection failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <View style={styles.container}>
            <Text style={styles.title}><FontAwesome5 name="dna" size={28} /> DermoAI</Text>
            <View style={styles.card}>
                <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#94a3b8" value={email} onChangeText={setEmail} autoCapitalize="none" />
                <TextInput style={styles.input} placeholder="Password" placeholderTextColor="#94a3b8" value={password} onChangeText={setPassword} secureTextEntry />

                <TouchableOpacity style={styles.btnPrimary} onPress={handleLogin} disabled={loading}>
                    {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Login</Text>}
                </TouchableOpacity>
                <TouchableOpacity onPress={() => navigation.navigate('Register')} style={{ marginTop: 15, alignItems: 'center' }}>
                    <Text style={styles.linkText}>Don't have an account? Register</Text>
                </TouchableOpacity>
            </View>
        </View>
    );
}

function RegisterScreen({ navigation }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('patient');
    const [specialty, setSpecialty] = useState('');
    const [achievement, setAchievement] = useState('');
    const [loading, setLoading] = useState(false);

    const handleReg = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, role, specialty, achievement })
            });
            if (res.ok) {
                Alert.alert("Success", "Registered! Please login.");
                navigation.navigate('Login');
            } else {
                const data = await res.json();
                Alert.alert("Error", data.detail);
            }
        } catch (e) {
            Alert.alert("Error", "Connection failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView contentContainerStyle={styles.scrollContainerCenter}>
            <Text style={styles.title}>Create Account</Text>
            <View style={styles.card}>
                <View style={{ flexDirection: 'row', marginBottom: 15, justifyContent: 'space-around' }}>
                    <TouchableOpacity onPress={() => setRole('patient')} style={[styles.tabBtn, role === 'patient' && styles.tabActive]}>
                        <Text style={[styles.tabText, role === 'patient' && styles.tabTextActive]}>Patient</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => setRole('doctor')} style={[styles.tabBtn, role === 'doctor' && styles.tabActive]}>
                        <Text style={[styles.tabText, role === 'doctor' && styles.tabTextActive]}>Doctor</Text>
                    </TouchableOpacity>
                </View>

                <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#94a3b8" value={email} onChangeText={setEmail} autoCapitalize="none" />
                <TextInput style={styles.input} placeholder="Password" placeholderTextColor="#94a3b8" value={password} onChangeText={setPassword} secureTextEntry />

                {role === 'doctor' && (
                    <>
                        <TextInput style={styles.input} placeholder="Specialty" placeholderTextColor="#94a3b8" value={specialty} onChangeText={setSpecialty} />
                        <TextInput style={styles.input} placeholder="Achievements" placeholderTextColor="#94a3b8" value={achievement} onChangeText={setAchievement} />
                    </>
                )}

                <TouchableOpacity style={styles.btnPrimary} onPress={handleReg} disabled={loading}>
                    {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Register</Text>}
                </TouchableOpacity>
                <TouchableOpacity onPress={() => navigation.goBack()} style={{ marginTop: 15, alignItems: 'center' }}>
                    <Text style={styles.linkText}>Back to Login</Text>
                </TouchableOpacity>
            </View>
        </ScrollView>
    );
}

// --- MOCK DATA ---
const CLINICAL_NEWS = [
    { id: '1', title: 'Breakthrough in Non-Invasive Melanoma Screening', src: 'Global Dermatology Foundation', date: '2h ago', link: 'https://www.aad.org' },
    { id: '2', title: 'AI Surpasses Expert Dermatologists in Identifying BCC', src: 'Tech in Medicine', date: '5h ago', link: 'https://www.nature.com/collections/fcaedgjhhf' },
    { id: '3', title: 'New Guidelines on Pediatric Skin Care Management', src: 'WHO Dermatology', date: '1d ago', link: 'https://www.who.int' }
];

// --- MAIN APP SCREENS ---

function AnalyzeScreen({ token }) {
    const [image, setImage] = useState(null);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);

    const pickImage = async () => {
        let res = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsEditing: true,
            aspect: [1, 1],
            quality: 1,
        });

        if (!res.canceled) {
            setImage(res.assets[0]);
            setResult(null);
        }
    };

    const analyze = async () => {
        if (!image) return;
        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', {
                uri: image.uri,
                name: 'photo.jpg',
                type: 'image/jpeg',
            });
            formData.append('token', token);

            const res = await fetch(`${API_URL}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'multipart/form-data' },
                body: formData,
            });

            const data = await res.json();
            if (res.ok) {
                setResult(data);
                setModalVisible(true);
            } else {
                Alert.alert("Analysis Failed", data.detail || "Server error");
            }
        } catch (e) {
            Alert.alert("Error", "Analysis Failed. Check Connection.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView contentContainerStyle={styles.scrollContainer}>
            {/* COLLABORATOR BADGE */}
            <View style={styles.collabBadge}>
                <FontAwesome5 name="shield-alt" size={14} color="#10b981" />
                <Text style={styles.collabText}>In collaboration with Global Dermatology Institute</Text>
            </View>

            <View style={styles.card}>
                <Text style={styles.cardTitle}>Instant Clinical Analysis</Text>
                <Text style={styles.cardSubTitle}>Upload a dermoscopic or clear skin lesion image for AI evaluation.</Text>

                <TouchableOpacity style={styles.uploadBox} onPress={pickImage}>
                    {image ? (
                        <Image source={{ uri: image.uri }} style={{ width: '100%', height: 220, borderRadius: 12 }} />
                    ) : (
                        <View style={{ alignItems: 'center' }}>
                            <View style={styles.iconCircle}>
                                <FontAwesome5 name="camera" size={30} color="#3b82f6" />
                            </View>
                            <Text style={{ color: '#94a3b8', marginTop: 15, fontWeight: '500' }}>Tap to scan skin lesion</Text>
                        </View>
                    )}
                </TouchableOpacity>

                <TouchableOpacity style={[styles.btnPrimary, { marginTop: 25, opacity: image ? 1 : 0.6 }]} onPress={analyze} disabled={!image || loading}>
                    {loading ? <ActivityIndicator color="#fff" /> : (
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center' }}>
                            <FontAwesome5 name="bolt" color="#fff" size={16} style={{ marginRight: 8 }} />
                            <Text style={styles.btnText}>Run AI Diagnostics</Text>
                        </View>
                    )}
                </TouchableOpacity>
            </View>

            {/* LIVE NEWS FEED */}
            <View style={{ marginTop: 10 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 15 }}>
                    <FontAwesome5 name="newspaper" size={18} color="#3b82f6" style={{ marginRight: 8 }} />
                    <Text style={{ color: '#fff', fontSize: 18, fontWeight: 'bold' }}>Clinical Research Feed</Text>
                </View>

                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ paddingBottom: 10 }}>
                    {CLINICAL_NEWS.map(item => (
                        <TouchableOpacity key={item.id} style={styles.newsCard} onPress={() => Linking.openURL(item.link)}>
                            <View style={styles.newsTag}>
                                <Text style={styles.newsDate}>{item.date}</Text>
                            </View>
                            <Text style={styles.newsTitle} numberOfLines={3}>{item.title}</Text>
                            <Text style={styles.newsSrc}>{item.src}</Text>
                        </TouchableOpacity>
                    ))}
                </ScrollView>
            </View>

            {/* Reuse ReportModal if result exists and modalVisible is true */}
            {result && (
                <ReportModal
                    visible={modalVisible}
                    onClose={() => setModalVisible(false)}
                    data={result}
                />
            )}
        </ScrollView>
    );
}

function HistoryScreen({ token }) {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedReport, setSelectedReport] = useState(null);

    const loadHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) setHistory(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => {
        loadHistory();
        // optionally add focus listener here refetching if requested
    }, [loadHistory]);

    const viewReport = async (id) => {
        try {
            const res = await fetch(`${API_URL}/history/${id}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) {
                // Formatting it similarly to what ReportModal expects
                setSelectedReport({
                    diagnosis: data.diagnosis,
                    report: data.report_text || 'Report data not available.',
                    // We don't save heatmap_base64 in DB currently per python code, 
                    // but we handle it gracefully if missing
                });
            }
        } catch (e) {
            Alert.alert("Error", "Could not load report");
        }
    };

    const renderItem = ({ item }) => (
        <View style={styles.card}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 }}>
                <Text style={{ color: '#94a3b8' }}>{new Date(item.date).toLocaleDateString()}</Text>
                <Text style={{
                    color: item.status === 'verified' ? '#10b981' : item.status === 'rejected' ? '#ef4444' : '#f59e0b',
                    fontWeight: 'bold',
                    textTransform: 'uppercase',
                    fontSize: 12
                }}>{item.status}</Text>
            </View>
            <Text style={{ color: '#fff', fontSize: 18, fontWeight: 'bold', marginBottom: 10 }}>{item.diagnosis}</Text>
            <TouchableOpacity style={styles.btnSecondary} onPress={() => viewReport(item.id)}>
                <Text style={styles.btnText}>View Report</Text>
            </TouchableOpacity>
        </View>
    );

    return (
        <View style={styles.container}>
            {loading ? <ActivityIndicator color="#3b82f6" /> : (
                <FlatList
                    data={history}
                    keyExtractor={item => item.id.toString()}
                    renderItem={renderItem}
                    contentContainerStyle={{ paddingBottom: 20 }}
                    ListEmptyComponent={<Text style={{ color: '#94a3b8', textAlign: 'center' }}>No history found</Text>}
                />
            )}

            {selectedReport && (
                <ReportModal
                    visible={!!selectedReport}
                    onClose={() => setSelectedReport(null)}
                    data={selectedReport}
                />
            )}
        </View>
    );
}

function DoctorsScreen({ token }) {
    const [doctors, setDoctors] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedDoctor, setSelectedDoctor] = useState(null);
    const [modalVisible, setModalVisible] = useState(false);

    useEffect(() => {
        loadDoctors();
    }, []);

    const loadDoctors = async () => {
        try {
            const res = await fetch(`${API_URL}/doctors`);
            const data = await res.json();
            if (res.ok) setDoctors(data);
        } catch (e) {
        } finally {
            setLoading(false);
        }
    };

    const scheduleMeet = (doc) => {
        setSelectedDoctor(doc);
        setModalVisible(true);
    };

    const renderItem = ({ item }) => (
        <View style={styles.card}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
                <View style={{ width: 50, height: 50, borderRadius: 25, backgroundColor: 'rgba(59, 130, 246, 0.2)', alignItems: 'center', justifyContent: 'center', marginRight: 15 }}>
                    <FontAwesome5 name="user-doctor" size={24} color="#3b82f6" />
                </View>
                <View>
                    <Text style={{ color: '#fff', fontSize: 18, fontWeight: 'bold' }}>{item.email.split('@')[0]}</Text>
                    <Text style={{ color: '#94a3b8' }}>{item.specialty || 'General Dermatologist'}</Text>
                </View>
            </View>
            <Text style={{ color: '#cbd5e1', marginBottom: 15, fontSize: 12 }}>{item.achievement || 'Expert analysis'}</Text>
            <TouchableOpacity style={styles.btnPrimary} onPress={() => scheduleMeet(item)}>
                <Text style={styles.btnText}>Schedule Meetup</Text>
            </TouchableOpacity>
        </View>
    );

    return (
        <View style={styles.container}>
            {loading ? <ActivityIndicator color="#3b82f6" /> : (
                <FlatList
                    data={doctors}
                    keyExtractor={item => item.id.toString()}
                    renderItem={renderItem}
                    contentContainerStyle={{ paddingBottom: 20 }}
                />
            )}

            {selectedDoctor && (
                <ScheduleModal
                    visible={modalVisible}
                    onClose={() => setModalVisible(false)}
                    doctor={selectedDoctor}
                    token={token}
                />
            )}
        </View>
    );
}

function CasesScreen({ token }) {
    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);

    const loadCases = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/cases/pending`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) setCases(data);
        } catch (e) {
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => {
        loadCases();
    }, [loadCases]);

    const acceptCase = async (id) => {
        try {
            const res = await fetch(`${API_URL}/cases/${id}/accept`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                Alert.alert("Success", "Case Accepted!");
                loadCases();
            }
        } catch (e) {
            Alert.alert("Error", "Could not accept case");
        }
    };

    const renderItem = ({ item }) => (
        <View style={styles.card}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 }}>
                <Text style={{ color: '#fff', fontWeight: 'bold', fontSize: 16 }}>Patient #{item.user_id}</Text>
            </View>
            <Text style={{ color: '#cbd5e1', marginBottom: 15 }}>{item.diagnosis}</Text>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <TouchableOpacity style={[styles.btnPrimary, { flex: 1, marginRight: 10 }]} onPress={() => acceptCase(item.id)}>
                    <Text style={styles.btnText}>Accept</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.btnSecondary, { flex: 1 }]} onPress={() => Alert.alert("Coming Soon", "File view not explicitly provided in API without ID yet.")}>
                    <Text style={styles.btnText}>View File</Text>
                </TouchableOpacity>
            </View>
        </View>
    );

    return (
        <View style={styles.container}>
            {loading ? <ActivityIndicator color="#3b82f6" /> : (
                <FlatList
                    data={cases}
                    keyExtractor={item => item.id.toString()}
                    renderItem={renderItem}
                    contentContainerStyle={{ paddingBottom: 20 }}
                    ListEmptyComponent={<Text style={{ color: '#94a3b8', textAlign: 'center' }}>No pending cases</Text>}
                />
            )}
        </View>
    );
}

function NotificationsScreen({ token }) {
    const [notifications, setNotifications] = useState([]);

    const loadNotifs = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/notifications`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) setNotifications(data);
        } catch (e) { }
    }, [token]);

    useEffect(() => {
        loadNotifs();
        // Polling logic to mimic live updates
        const interval = setInterval(() => {
            loadNotifs();
        }, 10000); // Poll every 10s on mobile for better experience

        return () => clearInterval(interval);
    }, [loadNotifs]);

    const renderItem = ({ item }) => (
        <View style={[styles.card, { flexDirection: 'row', alignItems: 'center' }]}>
            <FontAwesome5 name="info-circle" size={24} color="#3b82f6" style={{ marginRight: 15 }} />
            <View style={{ flex: 1 }}>
                <Text style={{ color: '#fff', fontSize: 15 }}>{item.message}</Text>
                <Text style={{ color: '#64748b', fontSize: 12, marginTop: 5 }}>{new Date(item.created_at).toLocaleString()}</Text>
            </View>
        </View>
    );

    return (
        <View style={styles.container}>
            <FlatList
                data={notifications}
                keyExtractor={item => item.id.toString()}
                renderItem={renderItem}
                contentContainerStyle={{ paddingBottom: 20 }}
                ListEmptyComponent={<Text style={{ color: '#94a3b8', textAlign: 'center' }}>No notifications</Text>}
            />
        </View>
    );
}

function ProfileScreen({ token, onLogout, role }) {
    const [user, setUser] = useState({});

    useEffect(() => {
        fetch(`${API_URL}/users/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()).then(setUser).catch(console.error);
    }, [token]);

    return (
        <ScrollView contentContainerStyle={styles.scrollContainer}>
            <View style={styles.card}>
                <View style={{ alignItems: 'center', marginBottom: 20 }}>
                    <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: '#1e293b', alignItems: 'center', justifyContent: 'center', marginBottom: 15 }}>
                        <FontAwesome5 name="user-alt" size={40} color="#3b82f6" />
                    </View>
                    <Text style={{ color: '#fff', fontSize: 22, fontWeight: 'bold' }}>{user.email}</Text>
                    <Text style={{ color: '#3b82f6', textTransform: 'uppercase', marginTop: 5 }}>{user.role}</Text>
                </View>

                <View style={{ borderTopWidth: 1, borderTopColor: '#1e293b', paddingTop: 20 }}>
                    {role === 'doctor' && (
                        <>
                            <View style={styles.profRow}><Text style={styles.profLabel}>Specialty:</Text><Text style={styles.profValue}>{user.specialty}</Text></View>
                            <View style={styles.profRow}><Text style={styles.profLabel}>Achievements:</Text><Text style={styles.profValue}>{user.achievement}</Text></View>
                        </>
                    )}
                    <View style={styles.profRow}><Text style={styles.profLabel}>Joined:</Text><Text style={styles.profValue}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</Text></View>
                </View>

                <TouchableOpacity style={[styles.btnPrimary, { backgroundColor: '#ef4444', marginTop: 30 }]} onPress={onLogout}>
                    <Text style={styles.btnText}>Logout</Text>
                </TouchableOpacity>
            </View>
        </ScrollView>
    );
}

// --- MODALS ---

function ScheduleModal({ visible, onClose, doctor, token }) {
    const [slotsData, setSlotsData] = useState([]);
    const [activeDayIdx, setActiveDayIdx] = useState(0);
    const [selectedSlot, setSelectedSlot] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (visible && doctor) loadSlots();
    }, [visible, doctor]);

    const loadSlots = async () => {
        try {
            const res = await fetch(`${API_URL}/doctors/${doctor.id}/slots`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok) {
                setSlotsData(data);
                setActiveDayIdx(0);
            }
        } catch (e) {
        } finally {
            setLoading(false);
        }
    };

    const confirmBooking = async () => {
        if (!selectedSlot) return;
        try {
            const res = await fetch(`${API_URL}/appointments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    doctor_id: doctor.id,
                    date: selectedSlot.date,
                    time: selectedSlot.time
                })
            });
            if (res.ok) {
                Alert.alert("Success", "Appointment Scheduled!");
                onClose();
            } else {
                const err = await res.json();
                Alert.alert("Failed", err.detail);
            }
        } catch (e) {
            Alert.alert("Error", "Connection to server failed.");
        }
    };

    if (!doctor) return null;

    const dayData = slotsData[activeDayIdx];

    return (
        <Modal visible={visible} animationType="slide" transparent={true}>
            <View style={styles.modalOverlay}>
                <View style={[styles.modalContent, { backgroundColor: '#ffffff' }]}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 20 }}>
                        <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#1e3a5f' }}>Schedule Meetup</Text>
                        <TouchableOpacity onPress={onClose}><FontAwesome5 name="times" size={20} color="#666" /></TouchableOpacity>
                    </View>

                    <View style={{ backgroundColor: '#f0f9ff', padding: 15, borderRadius: 8, borderLeftWidth: 4, borderLeftColor: '#3b82f6', marginBottom: 20 }}>
                        <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#1e40af' }}>Dr. {doctor.email.split('@')[0]}</Text>
                        <Text style={{ color: '#555' }}>{doctor.specialty}</Text>
                    </View>

                    {loading ? <ActivityIndicator /> : (
                        <>
                            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 20, maxHeight: 60 }}>
                                {slotsData.map((day, idx) => (
                                    <TouchableOpacity
                                        key={idx}
                                        style={[styles.dateTab, activeDayIdx === idx && styles.dateTabActive]}
                                        onPress={() => { setActiveDayIdx(idx); setSelectedSlot(null); }}
                                    >
                                        <Text style={[styles.dateTabText, activeDayIdx === idx && { color: '#fff' }]}>{day.day}</Text>
                                        <Text style={[styles.dateTabTextSmall, activeDayIdx === idx && { color: 'rgba(255,255,255,0.8)' }]}>
                                            {new Date(day.date).getDate()}
                                        </Text>
                                    </TouchableOpacity>
                                ))}
                            </ScrollView>

                            <Text style={{ fontWeight: 'bold', marginBottom: 10, color: '#333' }}>Available Slots</Text>
                            <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: 20 }}>
                                {dayData?.slots.map((s, idx) => (
                                    <TouchableOpacity
                                        key={idx}
                                        style={[styles.slotBtn,
                                        s.status === 'booked' && { backgroundColor: '#f1f5f9', opacity: 0.5, borderColor: '#e2e8f0' },
                                        selectedSlot?.time === s.time && { backgroundColor: '#3b82f6', borderColor: '#3b82f6' }
                                        ]}
                                        disabled={s.status === 'booked'}
                                        onPress={() => setSelectedSlot({ date: dayData.date, time: s.time })}
                                    >
                                        <Text style={[styles.slotBtnText,
                                        s.status === 'booked' && { color: '#94a3b8' },
                                        selectedSlot?.time === s.time && { color: '#fff' }
                                        ]}>{s.time}</Text>
                                    </TouchableOpacity>
                                ))}
                            </View>

                            <TouchableOpacity
                                style={[styles.btnPrimary, !selectedSlot && { opacity: 0.5 }]}
                                disabled={!selectedSlot}
                                onPress={confirmBooking}
                            >
                                <Text style={styles.btnText}>Confirm Booking</Text>
                            </TouchableOpacity>
                        </>
                    )}
                </View>
            </View>
        </Modal>
    );
}


function ReportModal({ visible, onClose, data }) {
    if (!data) return null;
    const isMalignant = data.diagnosis.toLowerCase() === 'malignant';

    return (
        <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
            <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', padding: 15, borderBottomWidth: 1, borderBottomColor: '#e2e8f0', alignItems: 'center' }}>
                    <Text style={{ fontWeight: 'bold', fontSize: 18, color: '#0f172a' }}>Medical Report</Text>
                    <TouchableOpacity onPress={onClose}><FontAwesome5 name="times" size={24} color="#64748b" /></TouchableOpacity>
                </View>

                <ScrollView contentContainerStyle={{ padding: 20 }}>
                    <View style={{ alignItems: 'center', marginBottom: 20 }}>
                        <FontAwesome5 name="hospital" size={40} color="#3b82f6" />
                        <Text style={{ fontWeight: 'bold', fontSize: 22, marginTop: 10, color: '#0f172a' }}>DermoAI Center</Text>
                    </View>

                    <View style={{ backgroundColor: '#fff', padding: 20, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, elevation: 3, marginBottom: 20 }}>
                        <Text style={{ fontSize: 12, color: '#64748b', fontWeight: 'bold', letterSpacing: 1 }}>CLASSIFICATION</Text>
                        <Text style={{ fontSize: 28, fontWeight: 'bold', color: '#0f172a', marginVertical: 10 }}>{data.diagnosis}</Text>

                        <View style={{ backgroundColor: isMalignant ? '#fef2f2' : '#f0fdf4', padding: 10, borderRadius: 8 }}>
                            <Text style={{ color: isMalignant ? '#b91c1c' : '#15803d', fontWeight: 'bold' }}>
                                {isMalignant ? "High Risk - Urgent Evaluation" : "Low Risk - Standard Follow-up"}
                            </Text>
                        </View>
                    </View>

                    {data.heatmap_base64 && (
                        <View style={{ backgroundColor: '#fff', padding: 20, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, elevation: 3, marginBottom: 20 }}>
                            <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#0f172a', marginBottom: 15 }}>AI Visualization (Grad-CAM)</Text>
                            <Image
                                source={{ uri: `data:image/png;base64,${data.heatmap_base64}` }}
                                style={{ width: '100%', height: 250, borderRadius: 8 }}
                                resizeMode="cover"
                            />
                        </View>
                    )}

                    <View style={{ backgroundColor: '#fff', padding: 20, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, elevation: 3 }}>
                        <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#0f172a', marginBottom: 15 }}>Clinical Analysis</Text>
                        <Text style={{ lineHeight: 24, color: '#334155' }}>{data.report.replace(/\*\*/g, '')}</Text>
                    </View>

                    <Text style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', marginTop: 30, marginBottom: 20 }}>
                        Disclaimer: This report is generated by AI and represents preliminary screening. It is NOT a medical diagnosis.
                    </Text>

                </ScrollView>
            </SafeAreaView>
        </Modal>
    );
}

// --- STYLES ---

const { width } = Dimensions.get('window');

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#0f172a', padding: width * 0.04 },
    centerContainer: { flex: 1, backgroundColor: '#0f172a', justifyContent: 'center', alignItems: 'center' },
    scrollContainer: { flexGrow: 1, backgroundColor: '#0f172a', padding: width * 0.04 },
    scrollContainerCenter: { flexGrow: 1, backgroundColor: '#0f172a', padding: width * 0.04, justifyContent: 'center' },
    title: { fontSize: width > 600 ? 40 : 32, color: '#fff', fontWeight: '900', marginBottom: 30, textAlign: 'center', letterSpacing: 1 },

    // Collaborative Badge
    collabBadge: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(16, 185, 129, 0.15)', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 20, marginBottom: 20, alignSelf: 'center', borderWidth: 1, borderColor: 'rgba(16, 185, 129, 0.3)' },
    collabText: { color: '#34d399', fontSize: 12, fontWeight: 'bold', marginLeft: 8 },

    // Dynamic Cards
    card: { backgroundColor: '#1e293b', padding: width * 0.05, borderRadius: 20, marginBottom: 20, shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 5, elevation: 8, borderWidth: 1, borderColor: '#334155' },
    cardTitle: { fontSize: width > 600 ? 24 : 20, color: '#fff', marginBottom: 5, fontWeight: 'bold' },
    cardSubTitle: { fontSize: 14, color: '#94a3b8', marginBottom: 20 },

    // Inputs & Buttons
    input: { backgroundColor: '#0f172a', color: '#fff', padding: 15, borderRadius: 12, marginBottom: 15, borderWidth: 1, borderColor: '#334155', fontSize: 16 },
    btnPrimary: { backgroundColor: '#3b82f6', padding: 16, borderRadius: 12, alignItems: 'center', shadowColor: '#3b82f6', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 4, elevation: 5 },
    btnSecondary: { backgroundColor: 'transparent', padding: 14, borderRadius: 12, alignItems: 'center', borderWidth: 1.5, borderColor: '#3b82f6' },
    btnText: { color: '#fff', fontWeight: 'bold', fontSize: 16, letterSpacing: 0.5 },
    linkText: { color: '#94a3b8', textAlign: 'center', marginTop: 10, fontSize: 14, fontWeight: '500' },

    // Upload Zone
    uploadBox: { height: 220, backgroundColor: 'rgba(15, 23, 42, 0.5)', borderRadius: 16, justifyContent: 'center', alignItems: 'center', borderStyle: 'dashed', borderWidth: 2, borderColor: '#475569' },
    iconCircle: { width: 70, height: 70, borderRadius: 35, backgroundColor: 'rgba(59, 130, 246, 0.2)', justifyContent: 'center', alignItems: 'center' },

    // News Feed Cards
    newsCard: { width: width * 0.65, backgroundColor: '#1e293b', padding: 15, borderRadius: 16, marginRight: 15, borderWidth: 1, borderColor: '#334155' },
    newsTag: { alignSelf: 'flex-start', backgroundColor: '#3b82f6', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, marginBottom: 10 },
    newsDate: { color: '#fff', fontSize: 10, fontWeight: 'bold' },
    newsTitle: { color: '#f8fafc', fontSize: 15, fontWeight: 'bold', marginBottom: 8, lineHeight: 22 },
    newsSrc: { color: '#94a3b8', fontSize: 12 },

    // Auth Tabs
    tabBtn: { flex: 1, padding: 12, alignItems: 'center', borderBottomWidth: 3, borderBottomColor: 'transparent' },
    tabActive: { borderBottomColor: '#3b82f6' },
    tabText: { color: '#94a3b8', fontWeight: 'bold', fontSize: 16 },
    tabTextActive: { color: '#3b82f6' },

    profRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 15, borderBottomWidth: 1, borderBottomColor: '#334155' },
    profLabel: { color: '#94a3b8', fontSize: 15 },
    profValue: { color: '#fff', fontWeight: 'bold', fontSize: 15 },

    // Modal
    modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: width * 0.05 },
    modalContent: { borderRadius: 16, padding: width * 0.06 },
    dateTab: { padding: 12, borderRadius: 12, marginRight: 10, borderWidth: 1, borderColor: '#e2e8f0', minWidth: 65, alignItems: 'center' },
    dateTabActive: { backgroundColor: '#3b82f6', borderColor: '#3b82f6', shadowColor: '#3b82f6', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 3 },
    dateTabText: { fontWeight: 'bold', color: '#334155', fontSize: 14 },
    dateTabTextSmall: { fontSize: 12, color: '#64748b', marginTop: 2 },
    slotBtn: { width: '30%', paddingVertical: 12, borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, alignItems: 'center', marginBottom: 12 },
    slotBtnText: { color: '#334155', fontWeight: '600' }
});
