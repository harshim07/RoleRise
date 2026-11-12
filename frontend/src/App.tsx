/// <reference types="vite/client" />
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { ArrowRight, Bell, BriefcaseBusiness, Bookmark, CalendarDays, Check, Compass, FileText, LogOut, MapPin, Pencil, Plus, Search, ShieldCheck, Sparkles, Trash2, X } from "lucide-react";
import { canWithdraw, statusClass } from "./domain";

declare global {
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

type User = { id: number; email: string };
type ScreeningQuestion = {id:string;label:string;type:"select"|"text";required?:boolean;options?:string[]};
type Job = { id: number; title: string; company: string; location: string; employment_type: string; experience: string; salary_range: string; skills: string; description: string; created_at?: string; is_open?: boolean; screening_questions?:ScreeningQuestion[]; match_tags?:string[]; match_score?:number };
type Application = { id: number; status: string; created_at: string; cover_letter?:string; candidate_email?:string; resume_filename?:string|null; screening_answers?:Record<string,string>; job: Job };
type ApplicationAction = {id:number;type:"interview"|"offer";status:string;scheduled_at:string|null;meeting_url:string;details:string;application_id:number;job_title:string;company:string};
type SavedSearch = {id:number;query:string;location:string;skill:string;employment_type:string;experience:string;is_active:boolean};
type CandidateProfileSummary = {full_name:string;phone:string;contact_email:string|null;email:string;resume_path:string|null;resume_filename:string|null;resume_uploaded_at:string|null;resume_content_type:string|null;resume_text:string};

// Replace the fallback URL below with your exact deployed backend URL if not set in Vercel Environment Variables
const api = (import.meta.env.VITE_API_BASE_URL || "https://role-rise-backend.onrender.com").replace(/\/+$/, "");
const tokenKey = "jt-access-token";

function routeFromLocation() {
  const path=window.location.pathname.replace(/\/+$/,"")||"/";
  if(new URLSearchParams(window.location.search).has("reset_token")||path==="/reset")return "reset";
  if(["/jobs","/saved","/dashboard","/profile","/notifications","/login","/register","/forgot"].includes(path))return path.slice(1)||"home";
  return path.startsWith("/jobs/")?"jobs":"home";
}
function routePath(page:string){return page==="home"?"/":`/${page}`;}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(tokenKey);
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${api}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail ?? "Something went wrong. Please try again.");
  return data as T;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState(routeFromLocation);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [employmentFilter, setEmploymentFilter] = useState("");
  const [experienceFilter, setExperienceFilter] = useState("");
  const [skillFilter, setSkillFilter] = useState("");
  const [sortOrder, setSortOrder] = useState("recommended");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [totalJobs, setTotalJobs] = useState(0);
  const [recommendations, setRecommendations] = useState<Job[]>([]);
  const [selected, setSelected] = useState<Job | null>(null);
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [actions, setActions] = useState<ApplicationAction[]>([]);
  const [saved, setSaved] = useState<Job[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [candidateProfile, setCandidateProfile] = useState<CandidateProfileSummary | null>(null);
  const [notices, setNotices] = useState<{id:number;message:string;is_read:boolean;created_at:string}[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadJobs(search = "", nextPage = 1) {
    try { const params=new URLSearchParams({q:search,location:locationFilter,employment_type:employmentFilter,experience:experienceFilter,skill:skillFilter,sort:sortOrder,page:String(nextPage),limit:"9"});const result = await request<{items:Job[];pages:number;total:number}>(`/jobs?${params}`); setJobs(result.items);setPageNumber(nextPage);setPageCount(result.pages);setTotalJobs(result.total); setError(""); }
    catch (e) { setError((e as Error).message); }
  }
  async function loadPrivate() {
    if (!user) return;
    try {
      const [apps, saves, notifications, recommended, currentActions, alerts, profile] = await Promise.all([request<Application[]>("/applications"), request<Job[]>("/saved-jobs"), request<typeof notices>("/notifications"), request<Job[]>("/recommendations"), request<ApplicationAction[]>("/applications/actions"), request<SavedSearch[]>("/saved-searches"), request<CandidateProfileSummary>("/profile")]);
      setApplications(apps); setSaved(saves); setNotices(notifications);setRecommendations(recommended);setActions(currentActions);setSavedSearches(alerts);setCandidateProfile(profile);
    } catch (e) { setError((e as Error).message); }
  }
  useEffect(() => {
    void loadJobs();
    const token = localStorage.getItem(tokenKey);
    if (token) request<User>("/auth/me").then(setUser).catch(() => localStorage.removeItem(tokenKey));
    const jobId=window.location.pathname.match(/^\/jobs\/(\d+)$/)?.[1];
    if(jobId)request<Job>(`/jobs/${jobId}`).then(setSelected).catch(e=>setError((e as Error).message));
    const onPopState=()=>{setPage(routeFromLocation());setSelectedApplication(null);const id=window.location.pathname.match(/^\/jobs\/(\d+)$/)?.[1];if(id)request<Job>(`/jobs/${id}`).then(setSelected).catch(e=>setError((e as Error).message));else setSelected(null);};
    window.addEventListener("popstate",onPopState);
    return ()=>window.removeEventListener("popstate",onPopState);
  }, []);
  useEffect(() => { void loadPrivate(); }, [user]);
  useEffect(() => {
    if (!user) return;
    let active = true;
    const refreshNotifications = async () => {
      try {
        const latest = await request<typeof notices>("/notifications");
        if (active) setNotices(latest);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    const interval = window.setInterval(() => void refreshNotifications(), 30000);
    window.addEventListener("focus", refreshNotifications);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshNotifications);
    };
  }, [user]);

  function navigate(next: string) { setPage(next); setSelected(null); setSelectedApplication(null); setError(""); setSuccess(""); const path=routePath(next);if(window.location.pathname!==path)window.history.pushState({}, "", path);window.scrollTo({top:0,behavior:"smooth"}); }
  function openJob(job:Job){setSelected(job);setPage("jobs");const path=`/jobs/${job.id}`;if(window.location.pathname!==path)window.history.pushState({}, "", path);window.scrollTo({top:0,behavior:"smooth"});}
  function closeJob(){setSelected(null);if(window.location.pathname.startsWith("/jobs/"))window.history.pushState({}, "", "/jobs");}
  async function authSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const isRegister = page === "register";
    try {
      const result = await request<{access_token:string;user:User}>(`/auth/${isRegister ? "register" : "login"}`, {method:"POST",body:JSON.stringify({email:form.get("email"),password:form.get("password"),...(isRegister?{full_name:form.get("name")}:{})})});
      localStorage.setItem(tokenKey,result.access_token); setUser(result.user); navigate("dashboard");
    } catch(e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function saveJob(job: Job) {
    try {
      if (!user) { navigate("login"); return; }
      const already = saved.some(item => item.id === job.id);
      await request(`/jobs/${job.id}/save`, {method:already?"DELETE":"POST"});
      setSaved(already?saved.filter(item=>item.id!==job.id):[job,...saved]);
      setSuccess(already?"Job removed from saved list":"Job saved for later");
    } catch(e) { setError((e as Error).message); }
  }
  async function applyJob(event: FormEvent<HTMLFormElement>, job: Job) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const screening_answers=Object.fromEntries((job.screening_questions??[]).map(question=>[question.id,String(form.get(`screening_${question.id}`)??"")]));
    setBusy(true);
    try {
      await request(`/jobs/${job.id}/apply`,{method:"POST",body:JSON.stringify({cover_letter:form.get("cover_letter"),screening_answers})});
      setSuccess("Application submitted. You can track its progress in your dashboard.");
      closeJob(); await loadPrivate();
    } catch(e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function toggleJobAlert(){
    if(!user){navigate("login");return;}
    const existing=savedSearches.find(item=>item.query===query&&item.location===locationFilter&&item.skill===skillFilter&&item.employment_type===employmentFilter&&item.experience===experienceFilter);
    try{
      if(existing){await request(`/saved-searches/${existing.id}`,{method:"DELETE"});setSuccess("Job alert turned off.");}
      else {await request("/saved-searches",{method:"POST",body:JSON.stringify({query,location:locationFilter,skill:skillFilter,employment_type:employmentFilter,experience:experienceFilter})});setSuccess("Job alert saved for this search.");}
      await loadPrivate();
    }catch(e){setError((e as Error).message);}
  }
  async function signOut() {
    let logoutError="";
    try { await request("/auth/logout",{method:"POST"}); } catch(e) { logoutError=(e as Error).message; }
    localStorage.removeItem(tokenKey); setUser(null); setApplications([]); setSaved([]); setActions([]);setSavedSearches([]);setCandidateProfile(null); navigate("home");
    if(logoutError)setError(logoutError);
  }

  const greeting = user?.email.split("@")[0] ?? "there";
  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/" onClick={e=>{e.preventDefault();navigate("home");}}><span className="brand-mark">RR</span><span>Role<span className="brand-light">Rise</span></span></a>
      <nav className="desktop-nav"><button onClick={()=>navigate("jobs")}>Find jobs</button><button onClick={()=>navigate(user?"saved":"login")}>Saved jobs</button><button onClick={()=>navigate(user?"dashboard":"login")}>My dashboard</button></nav>
      <div className="header-actions">{user?<><button className="icon-btn" aria-label="Notifications" onClick={()=>navigate("notifications")}><Bell size={18}/>{notices.some(n=>!n.is_read)&&<i/>}</button><button className="avatar" onClick={()=>navigate("profile")} aria-label="Open profile">{greeting.slice(0,1).toUpperCase()}</button><button className="sign-out" onClick={()=>void signOut()}><LogOut size={15}/> Sign out</button></>:<><button className="login-link" onClick={()=>navigate("login")}>Log in</button><button className="button button-dark nav-cta" onClick={()=>navigate("register")}>Get started <ArrowRight size={15}/></button></>}</div>
    </header>
    {error&&<div className="toast error-toast" role="alert">{error}<button onClick={()=>setError("")} aria-label="Dismiss"><X size={15}/></button></div>}
    {success&&<div className="toast success-toast" role="status"><Check size={16}/>{success}<button onClick={()=>setSuccess("")} aria-label="Dismiss"><X size={15}/></button></div>}
    {page==="home"&&<><main><section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot"/> YOUR NEXT CHAPTER STARTS HERE</div><h1>Find work that<br/>moves <span>you forward.</span></h1><p className="hero-subtitle">A better job search starts with the right opportunity. Discover roles where your talent makes a difference.</p>
        <form className="search-box" onSubmit={e=>{e.preventDefault();void loadJobs(query,1);navigate("jobs");}}><Search size={19}/><input aria-label="Job title or keyword" placeholder="Job title, skill or company" value={query} onChange={e=>setQuery(e.target.value)}/><span className="search-divider"/><MapPin size={18}/><input aria-label="Location" placeholder="City or remote" value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}/><button className="button button-accent">Search jobs <ArrowRight size={16}/></button></form>
        <div className="popular"><span>Popular:</span>{["Product Designer","Remote","Engineering","Marketing"].map(s=><button key={s} onClick={()=>{setQuery(s);void loadJobs(s,1);navigate("jobs");}}>{s}</button>)}</div></div>
        <div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="hero-card card-main"><div className="job-logo logo-blue">N</div><div><b>Senior Product Designer</b><p>Northstar · Remote</p></div><span className="match">Great match</span><div className="card-bottom"><span>Product design</span><span>Full-time</span><span>$120k–$160k</span></div></div><div className="hero-card card-float"><div className="float-icon"><Sparkles size={16}/></div><div><b>You're on the right track</b><p>Your profile is ready to shine.</p></div><Check className="float-check" size={18}/></div><div className="hero-avatars"><div className="avatar-stack"><span>M</span><span>A</span><span>J</span></div><p><strong>12k+</strong> people found their fit</p></div></div>
      </section>
      <section className="trust-row"><span>GOOD PEOPLE. GREAT PLACES.</span><div><b>northstar</b><b>layer<span>works</span></b><b className="trust-serif">venture&co.</b><b>◈ orbit</b><b>FABLE</b></div></section>
      <section className="section jobs-preview" id="how"><div className="section-heading"><div><div className="eyebrow">HANDPICKED FOR YOU</div><h2>Opportunities worth<br/>getting excited about.</h2></div><button className="text-link" onClick={()=>navigate("jobs")}>Explore all jobs <ArrowRight size={16}/></button></div>
        <JobGrid jobs={(recommendations.length?recommendations:jobs).slice(0,3)} onSelect={openJob} onSave={saveJob} saved={saved}/></section>
      <section className="steps-section"><div className="eyebrow">LESS SCROLLING. MORE THRIVING.</div><h2>A job search that just<br/>gets <span>you.</span></h2><div className="steps-grid">{[["01","Build your profile","Showcase the skills and experience that make you, you."],["02","Find your fit","Explore roles matched to where you want to go next."],["03","Make your move","Apply in minutes and track every step, all in one place."]].map(x=><article className="step-card" key={x[0]}><span>{x[0]}</span><h3>{x[1]}</h3><p>{x[2]}</p></article>)}</div></section>
      <section className="cta-panel"><div><div className="eyebrow">YOUR NEXT CHAPTER IS WAITING</div><h2>Ready to find your<br/>kind of opportunity?</h2><p>Make your next move a meaningful one.</p></div><button className="button button-accent" onClick={()=>navigate("register")}>Create your free account <ArrowRight size={17}/></button><div className="cta-decoration">RR</div></section></main><Footer onNavigate={navigate}/></>}
    {page==="login"&&<AuthPage mode="login" onSubmit={authSubmit} busy={busy} onSwitch={()=>navigate("register")} onForgot={()=>navigate("forgot")}/>}
    {page==="register"&&<AuthPage mode="register" onSubmit={authSubmit} busy={busy} onSwitch={()=>navigate("login")}/>}
    {page==="forgot"&&<PasswordPage mode="forgot" onDone={()=>navigate("login")} setError={setError} setSuccess={setSuccess}/>}
    {page==="reset"&&<PasswordPage mode="reset" token={new URLSearchParams(window.location.search).get("reset_token")??new URLSearchParams(window.location.search).get("token")??""} onDone={()=>navigate("login")} setError={setError} setSuccess={setSuccess}/>}
    {page==="jobs"&&<main className="page-wrap jobs-page">{user&&<section className="recommended-section"><div className="section-heading compact"><div><div className="page-eyebrow">MATCHED TO YOUR PROFILE</div><h2>Recommended for you</h2><p className="page-lead">Roles matched to your skills and job preferences.</p></div></div><JobGrid jobs={recommendations.slice(0,3)} onSelect={openJob} onSave={saveJob} saved={saved}/></section>}<div className="page-eyebrow">FIND YOUR NEXT MOVE</div><h1 className="page-title">Explore open roles</h1><p className="page-lead">Real opportunities from teams ready to meet you.</p><form className="jobs-search" onSubmit={e=>{e.preventDefault();void loadJobs(query,1);}}><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search title, skill or company"/><button className="button button-dark">Search</button></form><div className="filter-row"><input aria-label="Filter by location" value={locationFilter} onChange={e=>setLocationFilter(e.target.value)} placeholder="Filter by location"/><input aria-label="Filter by skill" value={skillFilter} onChange={e=>setSkillFilter(e.target.value)} placeholder="Filter by skill"/><input aria-label="Filter by experience" value={experienceFilter} onChange={e=>setExperienceFilter(e.target.value)} placeholder="Filter by experience"/><select aria-label="Employment type" value={employmentFilter} onChange={e=>setEmploymentFilter(e.target.value)}><option value="">All employment types</option><option>Full-time</option><option>Part-time</option><option>Contract</option><option>Internship</option><option>Temporary</option></select><select aria-label="Sort jobs" value={sortOrder} onChange={e=>setSortOrder(e.target.value)}><option value="recommended">Recommended</option><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="company">Company name</option></select><button type="button" className="button button-outline" onClick={()=>void loadJobs(query,1)}>Apply filters</button></div><div className="job-alert-row"><span><b>Get Job Alerts</b><small>Save this search and keep an eye on new matching roles.</small></span><button type="button" className={`alert-toggle ${savedSearches.some(item=>item.query===query&&item.location===locationFilter&&item.skill===skillFilter&&item.employment_type===employmentFilter&&item.experience===experienceFilter)?"active":""}`} role="switch" aria-checked={savedSearches.some(item=>item.query===query&&item.location===locationFilter&&item.skill===skillFilter&&item.employment_type===employmentFilter&&item.experience===experienceFilter)} onClick={()=>void toggleJobAlert()}><i/></button></div><div className="results-meta"><strong>{totalJobs}</strong> {totalJobs===1?"opportunity":"opportunities"} to explore</div><JobGrid jobs={jobs} onSelect={openJob} onSave={saveJob} saved={saved}/>{pageCount>1&&<div className="pagination"><button className="button button-outline" disabled={pageNumber<=1} onClick={()=>void loadJobs(query,pageNumber-1)}>Previous</button><span>Page {pageNumber} of {pageCount}</span><button className="button button-outline" disabled={pageNumber>=pageCount} onClick={()=>void loadJobs(query,pageNumber+1)}>Next</button></div>}</main>}
    {page==="dashboard"&&<main className="page-wrap"><div className="dashboard-welcome"><div><div className="page-eyebrow">YOUR JOB SEARCH, ALL IN ONE PLACE</div><h1 className="page-title">Good to see you, {greeting}.</h1><p className="page-lead">Keep your momentum going. Your next opportunity could be one application away.</p></div><button className="button button-accent" onClick={()=>navigate("jobs")}>Find a job <ArrowRight size={16}/></button></div><div className="stats-row"><Stat label="Applications" value={applications.length} icon={<FileText/>}/><Stat label="In progress" value={applications.filter(a=>["Under Review","Shortlisted","Interview Scheduled","Interview","Offer"].includes(a.status)).length} icon={<Compass/>}/><Stat label="Saved roles" value={saved.length} icon={<Bookmark/>}/></div><ActionPanel actions={actions} onError={setError} onChanged={()=>void loadPrivate()}/><div className="section-heading compact"><h2>Your applications</h2><button className="text-link" onClick={()=>navigate("jobs")}>Browse roles <ArrowRight size={15}/></button></div><ApplicationList applications={applications} onSelect={setSelectedApplication}/></main>}
    {page==="saved"&&<main className="page-wrap"><div className="page-eyebrow">A LITTLE INSPIRATION FOR LATER</div><h1 className="page-title">Saved jobs</h1><p className="page-lead">Roles you bookmarked for the next step in your search.</p>{saved.length?<JobGrid jobs={saved} onSelect={openJob} onSave={saveJob} saved={saved}/>:<Empty text="You haven't saved any jobs yet. Save a role to keep it close for later."/>}</main>}
    {page==="profile"&&<ProfilePage onDone={()=>navigate("dashboard")} setError={setError} setSuccess={setSuccess}/>}
    {page==="notifications"&&<main className="page-wrap narrow"><div className="notification-heading"><div><div className="page-eyebrow">STAY IN THE LOOP</div><h1 className="page-title">Notifications</h1></div>{notices.some(n=>!n.is_read)&&<button className="button button-outline" onClick={async()=>{try{await request("/notifications/read-all",{method:"POST"});setNotices(notices.map(n=>({...n,is_read:true})));}catch(e){setError((e as Error).message);}}}>Mark all as read</button>}</div>{notices.map(n=><div className={`notice-row ${n.is_read?"is-read":""}`} key={n.id}><span className={n.is_read?"notice-dot read":"notice-dot"}/><div className="notice-copy"><p>{n.message}</p><time>{new Date(n.created_at).toLocaleString()}</time></div>{!n.is_read&&<button className="text-link" onClick={async()=>{try{await request(`/notifications/${n.id}/read`,{method:"POST"});setNotices(notices.map(x=>x.id===n.id?{...x,is_read:true}:x));}catch(e){setError((e as Error).message);}}}>Mark read</button>}</div>)}{notices.length===0&&<Empty text="You're all caught up. New updates will show up here."/>}</main>}
    {selected&&<JobDetailModal job={selected} user={user} profile={candidateProfile} recommendations={recommendations} availableJobs={jobs} saved={saved} busy={busy} onClose={closeJob} onApply={applyJob} onSelect={openJob} onSave={saveJob} onProfile={()=>navigate("profile")} onRegister={()=>navigate("register")}/>}
    {selectedApplication&&<ApplicationStatusModal application={selectedApplication} actions={actions.filter(action=>action.application_id===selectedApplication.id)} onClose={()=>setSelectedApplication(null)} onError={setError} onWithdraw={async()=>{try{await request(`/applications/${selectedApplication.id}/withdraw`,{method:"POST"});setSelectedApplication(null);await loadPrivate();setSuccess("Application withdrawn.");}catch(e){setError((e as Error).message);}}}/>}
    <button className="mobile-saved" onClick={()=>navigate(user?"saved":"login")} aria-label="Saved jobs"><Bookmark size={18}/></button>
  </div>;
}

function JobGrid({jobs,onSelect,onSave,saved}:{jobs:Job[];onSelect:(j:Job)=>void;onSave:(j:Job)=>void;saved:Job[]}) {
  if (!jobs.length) return <Empty text="No roles found just yet. Try another search or check back soon."/>;
  return <div className="job-grid">{jobs.map(job=><article className="job-card" key={job.id}><div className="job-card-top"><div className={`job-logo ${job.company.length%2?"logo-blue":"logo-purple"}`}>{job.company.slice(0,1)}</div><button className={`save-button ${saved.some(x=>x.id===job.id)?"saved":""}`} aria-label="Save job" onClick={()=>onSave(job)}><Bookmark size={18}/></button></div><div className="job-type">{job.employment_type} <span>·</span> {job.experience}</div><h3>{job.title}</h3><p className="company-line">{job.company}</p><p className="location-line"><MapPin size={14}/>{job.location}</p>{job.match_tags&&job.match_tags.length>0&&<div className="match-tags">{job.match_tags.slice(0,3).map(tag=><span key={tag}>{tag}</span>)}</div>}<div className="job-card-bottom"><span>{job.salary_range||"Competitive salary"}</span><button onClick={()=>onSelect(job)} aria-label={`View ${job.title}`}>View role <ArrowRight size={15}/></button></div></article>)}</div>;
}

function JobDetailModal({job,user,profile,recommendations,availableJobs,saved,busy,onClose,onApply,onSelect,onSave,onProfile,onRegister}:{job:Job;user:User|null;profile:CandidateProfileSummary|null;recommendations:Job[];availableJobs:Job[];saved:Job[];busy:boolean;onClose:()=>void;onApply:(event:FormEvent<HTMLFormElement>,job:Job)=>void;onSelect:(job:Job)=>void;onSave:(job:Job)=>void;onProfile:()=>void;onRegister:()=>void}) {
  const similar=[...recommendations,...availableJobs].filter((item,index,array)=>item.id!==job.id&&array.findIndex(other=>other.id===item.id)===index).slice(0,3);
  const questions=job.screening_questions??[];
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><section className="job-modal job-detail-modal"><button className="modal-close" onClick={onClose} aria-label="Close"><X size={20}/></button><div className="job-logo logo-blue">{job.company.slice(0,1)}</div><h2>{job.title}</h2><p className="modal-company">{job.company} · {job.location}</p><div className="job-tags"><span>{job.employment_type}</span><span>{job.experience}</span>{job.salary_range&&<span>{job.salary_range}</span>}</div><h3>About the role</h3><p className="modal-description">{job.description}</p><h3>What you’ll bring</h3><p>{job.skills||"Bring your experience and curiosity."}</p>{user?<><div className="application-preview"><h3>Before you apply</h3><p><b>Email:</b> {profile?.contact_email||profile?.email||user.email}</p><p><b>Resume:</b> {profile?.resume_filename||"No resume attached"}{profile?.resume_uploaded_at?` · Uploaded ${new Date(profile.resume_uploaded_at).toLocaleDateString()}`:""}</p>{profile?.resume_path?<details><summary>Preview attached resume</summary><ResumeDocument profile={profile}/></details>:<button className="text-link" onClick={onProfile}>Add resume in your profile</button>}</div><form className="apply-form" onSubmit={e=>onApply(e,job)}>{questions.length>0&&<fieldset className="screening-questions"><legend>Screening questions</legend>{questions.map(question=><label key={question.id}>{question.label}{question.type==="select"?<select name={`screening_${question.id}`} required={question.required!==false}><option value="">Select an answer</option>{(question.options??[]).map(option=><option key={option}>{option}</option>)}</select>:<input name={`screening_${question.id}`} required={question.required!==false} maxLength={1000}/>}</label>)}</fieldset>}<label htmlFor="cover">A note to the hiring team <span>Optional</span></label><textarea id="cover" name="cover_letter" rows={4} maxLength={5000} placeholder="Tell them what excites you about this role..."/><button disabled={busy} className="button button-accent">{busy?"Submitting…":"Submit application"} <ArrowRight size={16}/></button></form></>:<button className="button button-accent" onClick={onRegister}>Create an account to apply <ArrowRight size={16}/></button>}
    <section className="similar-roles"><div className="section-heading compact"><h3>Similar roles you might like</h3></div><JobGrid jobs={similar} onSelect={onSelect} onSave={onSave} saved={saved}/></section>
  </section></div>;
}
function AuthPage({mode,onSubmit,busy,onSwitch,onForgot}:{mode:"login"|"register";onSubmit:(e:FormEvent<HTMLFormElement>)=>void;busy:boolean;onSwitch:()=>void;onForgot?:(email:string)=>void}) {
  const [email,setEmail]=useState("");
  return <main className="auth-page"><div className="auth-panel"><a className="brand auth-brand"><span className="brand-mark">RR</span><span>Role<span className="brand-light">Rise</span></span></a><div className="page-eyebrow">{mode==="login"?"WELCOME BACK":"YOUR NEXT CHAPTER"}</div><h1>{mode==="login"?"Good things start here.":"Your next move starts here."}</h1><p>{mode==="login"?"Sign in to pick up where you left off.":"Create your account and meet your next opportunity."}</p><form className="auth-form" onSubmit={onSubmit}>{mode==="register"&&<label>Full name<input name="name" required minLength={2} maxLength={160} placeholder="Your name"/></label>}<label>Email address<input name="email" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label><label>Password<input name="password" type="password" required minLength={10} autoComplete={mode==="login"?"current-password":"new-password"} placeholder="At least 10 characters"/></label>{mode==="login"&&<button type="button" className="forgot-link" onClick={()=>onForgot?.(email)}>Forgot password?</button>}<button disabled={busy} className="button button-dark auth-submit">{busy?"Just a moment...":mode==="login"?"Log in":"Create your account"} <ArrowRight size={16}/></button></form><div className="auth-switch">{mode==="login"?"New to RoleRise?":"Already have an account?"}<button onClick={onSwitch}>{mode==="login"?"Create an account":"Log in"}</button></div><div className="secure-note"><ShieldCheck size={16}/>Your information is encrypted and secure.</div></div><aside className="auth-aside"><div className="aside-glow"/><div className="eyebrow">FIND A PLACE TO DO YOUR BEST WORK</div><h2>Good work<br/>should feel<br/><span>good.</span></h2><p>Find teams that see your potential and opportunities that fit the life you want to build.</p><div className="aside-note"><Sparkles size={17}/><span><b>One thoughtful application at a time.</b><br/>Your search, your pace, your next chapter.</span></div></aside></main>;
}
function PasswordPage({mode,token="",onDone,setError,setSuccess}:{mode:"forgot"|"reset";token?:string;onDone:()=>void;setError:(s:string)=>void;setSuccess:(s:string)=>void}) {
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=Object.fromEntries(new FormData(event.currentTarget).entries());try{await request(mode==="forgot"?"/auth/forgot-password":"/auth/reset-password",{method:"POST",body:JSON.stringify(mode==="forgot"?{email:form.email}:{token,password:form.password})});setSuccess(mode==="forgot"?"If that account exists, reset instructions will be sent.":"Password updated. Please sign in.");if(mode==="reset")onDone();}catch(e){setError((e as Error).message);}}
  return <main className="auth-page"><section className="auth-panel"><a className="brand auth-brand" href="/" onClick={e=>{e.preventDefault();onDone();}}><span className="brand-mark">RR</span><span>Role<span className="brand-light">Rise</span></span></a><div className="page-eyebrow">ACCOUNT RECOVERY</div><h1>{mode==="forgot"?"Reset your password.":"Choose a new password."}</h1><p>{mode==="forgot"?"We'll email a secure reset link if an account matches.":"Your reset link expires 30 minutes after it was sent."}</p><form className="auth-form" onSubmit={e=>void submit(e)}>{mode==="forgot"?<label>Email address<input name="email" type="email" autoComplete="email" required/></label>:<label>New password<input name="password" type="password" minLength={10} maxLength={128} autoComplete="new-password" required placeholder="At least 10 characters"/></label>}<button className="button button-dark auth-submit">{mode==="forgot"?"Send reset link":"Update password"} <ArrowRight size={16}/></button></form><button className="text-link profile-back" onClick={onDone}>Back to sign in</button></section></main>;
}
function ApplicationList({applications,onSelect}:{applications:Application[];onSelect:(application:Application)=>void}) {
  if(!applications.length)return <Empty text="Your next opportunity is waiting. Start exploring roles that fit you."/>;
  return <div className="application-list">{applications.map(application=><button type="button" className="application-row application-clickable" key={application.id} onClick={()=>onSelect(application)}><span className="job-logo logo-blue">{application.job.company.slice(0,1)}</span><span className="application-main"><b>{application.job.title}</b><small>{application.job.company} · {application.job.location}</small></span><span className={`status-badge ${statusClass(application.status)}`}>{application.status}</span><span className="application-open">View timeline <ArrowRight size={14}/></span></button>)}</div>;
}
function ApplicationStatusModal({application,actions,onClose,onError,onWithdraw}:{application:Application;actions:ApplicationAction[];onClose:()=>void;onError:(message:string)=>void;onWithdraw:()=>void}) {
  const [timeline,setTimeline]=useState<{status:string;note:string;created_at:string}[]>([]);
  useEffect(()=>{request<typeof timeline>(`/applications/${application.id}/history`).then(setTimeline).catch(e=>onError((e as Error).message));},[application.id]);
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><section className="job-modal status-modal"><button className="modal-close" onClick={onClose} aria-label="Close"><X size={20}/></button><div className="page-eyebrow">APPLICATION TRACKING</div><h2>{application.job.title}</h2><p className="modal-company">{application.job.company} · Submitted {new Date(application.created_at).toLocaleDateString()}</p><h3>Application status timeline</h3>{timeline.length?<ol className="status-timeline">{timeline.map((event,index)=><li key={`${event.status}-${event.created_at}-${index}`}><span className="timeline-dot"/><div><b>{event.status}</b><time>{new Date(event.created_at).toLocaleString()}</time>{event.note&&<p>{event.note}</p>}</div></li>)}</ol>:<Empty text="Status updates will appear here when the hiring team shares them."/>}<h3>Application details</h3><div className="application-answer"><p><b>Email:</b> {application.candidate_email||"—"}</p><p><b>Resume:</b> {application.resume_filename||"No resume attached"}</p>{application.cover_letter&&<p><b>Note:</b> {application.cover_letter}</p>}{Object.entries(application.screening_answers??{}).map(([key,value])=><p key={key}><b>{application.job.screening_questions?.find(question=>question.id===key)?.label??key}:</b> {value}</p>)}</div>{actions.map(action=><div className="action-inline" key={action.id}><b>{action.type==="offer"?"Offer":"Interview"}: {action.status.replaceAll("_"," ")}</b>{action.details&&<p>{action.details}</p>}{action.scheduled_at&&<p>{new Date(action.scheduled_at).toLocaleString()}</p>}{action.meeting_url&&<a href={action.meeting_url} target="_blank" rel="noreferrer">Open meeting link</a>}</div>)}{canWithdraw(application.status)&&<button className="button button-outline withdraw-application" onClick={onWithdraw}>Withdraw application</button>}</section></div>;
}
function localDateTimeMin(){const date=new Date(Date.now()+60*60*1000);date.setMinutes(date.getMinutes()-date.getTimezoneOffset());return date.toISOString().slice(0,16);}
function ActionPanel({actions,onError,onChanged}:{actions:ApplicationAction[];onError:(message:string)=>void;onChanged:()=>void}) {
  const [booking,setBooking]=useState<number|null>(null);
  async function book(event:FormEvent<HTMLFormElement>,action:ApplicationAction){event.preventDefault();const form=new FormData(event.currentTarget);const date=String(form.get("scheduled_at")||"");try{await request(`/application-actions/${action.id}/book`,{method:"PUT",body:JSON.stringify({scheduled_at:new Date(date).toISOString()})});setBooking(null);onChanged();}catch(e){onError((e as Error).message);}}
  async function accept(action:ApplicationAction){try{await request(`/application-actions/${action.id}/accept`,{method:"POST"});onChanged();}catch(e){onError((e as Error).message);}}
  return <section className="action-panel"><div className="section-heading compact"><div><div className="page-eyebrow">NEXT STEPS</div><h2>Action required / Interviews</h2></div></div>{actions.length===0?<Empty text="No interviews or offers need your attention right now."/>:<div className="action-grid">{actions.map(action=><article className="action-card" key={action.id}><span className={`action-kind ${action.type}`}>{action.type==="interview"?"Interview":"Offer"}</span><h3>{action.job_title}</h3><p className="company-line">{action.company}</p>{action.details&&<p className="action-details">{action.details}</p>}{action.type==="interview"&&action.status==="action_required"&&<>{booking===action.id?<form className="booking-form" onSubmit={e=>void book(e,action)}><label>Choose a time<input type="datetime-local" name="scheduled_at" min={localDateTimeMin()} required/></label><button className="button button-dark">Book interview</button></form>:<button className="button button-outline" onClick={()=>setBooking(action.id)}>Choose interview time</button>}</>}{action.type==="interview"&&action.status==="booked"&&<><p className="action-time">Booked: {action.scheduled_at?new Date(action.scheduled_at).toLocaleString():"—"}</p>{action.meeting_url&&<a href={action.meeting_url} target="_blank" rel="noreferrer">Join meeting <ArrowRight size={14}/></a>}</>}{action.type==="offer"&&action.status==="action_required"&&<button className="button button-dark" onClick={()=>void accept(action)}>Accept offer</button>}{action.type==="offer"&&action.status==="accepted"&&<span className="status-badge selected">Offer accepted</span>}</article>)}</div>}</section>;
}
function Stat({label,value,icon}:{label:string;value:number;icon:ReactNode}) {return <article className="stat-card"><span className="stat-icon">{icon}</span><span className="stat-value">{value}</span><span className="stat-label">{label}</span></article>;}
function Empty({text}:{text:string}) {return <div className="empty-state"><div><BriefcaseBusiness size={21}/></div><p>{text}</p></div>;}
type EducationEntry = {id:number;institution:string;degree:string;field_of_study:string;start_year:number|null;end_year:number|null};
type ExperienceEntry = {id:number;company:string;title:string;location:string;start_date:string;end_date:string;description:string};
type EducationInput = Omit<EducationEntry,"id">;
type ExperienceInput = Omit<ExperienceEntry,"id">;
type ProfileData = { [key:string]:unknown; email?:string; contact_email?:string|null; phone?:string; full_name?:string; location?:string; summary?:string; skills?:string; linkedin_url?:string; github_url?:string; portfolio_url?:string; preferred_roles?:string; work_mode?:string; expected_salary?:string; notice_period?:string; completion?:number; resume_path?:string|null; resume_filename?:string|null; resume_content_type?:string|null; resume_uploaded_at?:string|null; resume_text?:string; education?:EducationEntry[]; experience?:ExperienceEntry[] };
function calculateProfileStrength(profile:ProfileData){
  return (profile.full_name?8:0)+(profile.phone?7:0)+(profile.contact_email||profile.email?7:0)+(profile.location?4:0)+
    (profile.summary?8:0)+(profile.skills?8:0)+(profile.linkedin_url||profile.github_url||profile.portfolio_url?4:0)+
    (profile.experience?.length?14:0)+(profile.education?.length?10:0)+(profile.resume_path?10:0)+
    (profile.preferred_roles?8:0)+(profile.work_mode?5:0)+(profile.expected_salary?4:0)+(profile.notice_period?3:0);
}
function ResumeDocument({profile}:{profile:Pick<ProfileData,"resume_path"|"resume_content_type"|"resume_text">}) {
  const [previewUrl,setPreviewUrl]=useState("");
  const [previewFailed,setPreviewFailed]=useState(false);
  useEffect(()=>{
    let active=true;
    let objectUrl="";
    setPreviewUrl("");
    setPreviewFailed(false);
    if(profile.resume_path&&profile.resume_content_type==="application/pdf"){
      const headers=new Headers();
      const token=localStorage.getItem(tokenKey);
      if(token)headers.set("Authorization",`Bearer ${token}`);
      fetch(`${api}/profile/resume`,{headers}).then(response=>{
        if(!response.ok)throw new Error("Resume preview is unavailable");
        return response.blob();
      }).then(blob=>{objectUrl=URL.createObjectURL(blob);if(active)setPreviewUrl(objectUrl);}).catch(()=>{if(active)setPreviewFailed(true);});
    }
    return ()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl);};
  },[profile.resume_path,profile.resume_content_type]);
  if(profile.resume_content_type==="application/pdf")return previewFailed?<p className="page-lead">Resume preview could not be loaded. Try removing and uploading the file again.</p>:previewUrl?<iframe className="resume-preview-frame" title="Resume PDF preview" src={previewUrl}/>:<p className="page-lead">Loading resume preview…</p>;
  if(profile.resume_text)return <pre className="resume-text-preview">{profile.resume_text.slice(0,6000)}</pre>;
  return <p className="page-lead">No preview is available for this document.</p>;
}
function ProfilePage({onDone,setError,setSuccess}:{onDone:()=>void;setError:(s:string)=>void;setSuccess:(s:string)=>void}) {
  const [profile,setProfile]=useState<ProfileData>({});
  const [loaded,setLoaded]=useState(false);
  const [saving,setSaving]=useState(false);
  const [addingEducation,setAddingEducation]=useState(false);
  const [addingExperience,setAddingExperience]=useState(false);
  const [editingEducation,setEditingEducation]=useState<number|null>(null);
  const [editingExperience,setEditingExperience]=useState<number|null>(null);
  async function refresh(){try{setProfile(await request<ProfileData>("/profile"));}catch(e){setError((e as Error).message);}finally{setLoaded(true);}}
  useEffect(()=>{void refresh();},[]);
  async function save(e:FormEvent<HTMLFormElement>){e.preventDefault();setSaving(true);const form=Object.fromEntries(new FormData(e.currentTarget).entries());try{await request("/profile",{method:"PUT",body:JSON.stringify(form)});setSuccess("Your profile has been saved.");await refresh();}catch(e){setError((e as Error).message);}finally{setSaving(false);}}
  async function upload(e:FormEvent<HTMLFormElement>){e.preventDefault();const formElement=e.currentTarget;const form=new FormData(formElement);try{const result=await request<{parsed:Record<string,string>}>("/profile/resume",{method:"POST",body:form});await refresh();formElement.reset();const count=Object.values(result.parsed).filter(Boolean).length;setSuccess(count===1?"Resume uploaded. Parsed 1 profile detail; review it below.":`Resume uploaded. Parsed ${count} profile details; review them below.`);}catch(e){setError((e as Error).message);}}
  async function removeResume(){if(!window.confirm("Remove your uploaded resume?"))return;try{await request("/profile/resume",{method:"DELETE"});await refresh();setSuccess("Resume removed.");}catch(e){setError((e as Error).message);}}
  async function saveRecord(kind:"education"|"experience",value:EducationInput|ExperienceInput,id?:number){try{await request(`/profile/${kind}${id?`/${id}`:""}`,{method:id?"PUT":"POST",body:JSON.stringify(value)});await refresh();setAddingEducation(false);setAddingExperience(false);setEditingEducation(null);setEditingExperience(null);setSuccess(`${kind==="education"?"Education":"Experience"} ${id?"updated":"added"}.`);}catch(e){setError((e as Error).message);}}
  async function removeRecord(kind:"education"|"experience",id:number){if(!window.confirm(`Remove this ${kind==="education"?"education":"experience"} record?`))return;try{await request(`/profile/${kind}/${id}`,{method:"DELETE"});await refresh();setSuccess(`${kind==="education"?"Education":"Experience"} removed.`);}catch(e){setError((e as Error).message);}}
  const fields:[string,string,string][]=[["full_name","Full name","Your name"],["contact_email","Contact email","you@example.com"],["phone","Phone","Phone number"],["location","Location","City or remote"],["skills","Skills","React, product strategy, SQL"],["linkedin_url","LinkedIn URL","https://linkedin.com/in/..."],["github_url","GitHub URL","https://github.com/..."],["portfolio_url","Portfolio URL","https://..."]];
  const experience=[...(profile.experience??[])].sort((a,b)=>experienceSortDate(b.end_date).localeCompare(experienceSortDate(a.end_date))||experienceSortDate(b.start_date).localeCompare(experienceSortDate(a.start_date)));
  const education=[...(profile.education??[])].sort((a,b)=>(b.end_year??9999)-(a.end_year??9999)||(b.start_year??0)-(a.start_year??0));
  const completion=calculateProfileStrength(profile);
  if(!loaded)return <main className="page-wrap profile-page"><p className="page-lead">Loading your profile…</p></main>;
  return <main className="page-wrap profile-page">
    <header className="profile-heading"><div><div className="page-eyebrow">MAKE A GREAT FIRST IMPRESSION</div><h1 className="page-title">Your profile</h1><p className="page-lead">Keep your experience up to date so the right opportunities can find you.</p></div><button className="button button-outline profile-back-top" onClick={onDone}>Back to dashboard</button></header>
    <section className="profile-progress"><div className="progress-copy"><span className="progress-icon"><Check size={18}/></span><div><b>Profile strength</b><p>A complete profile helps employers get to know you.</p></div></div><strong>{completion}%</strong><div className="progress-track"><span style={{width:`${completion}%`}}/></div></section>
    <form id="profile-details-form" onSubmit={e=>void save(e)}>
      <section className="profile-section">
        <div className="profile-section-heading"><div><span className="section-kicker">ABOUT YOU</span><h2>Personal details</h2><p>Your contact information, skills, and professional links.</p></div></div>
        <div className="profile-form profile-details">
          {fields.map(([name,label,placeholder])=><label key={name} className={["skills","linkedin_url","github_url","portfolio_url"].includes(name)?"profile-wide":""}>{label}<input name={name} type={name==="contact_email"?"email":name.endsWith("_url")?"url":"text"} value={String(profile[name]??(name==="contact_email"?profile.email:"")??"")} onChange={e=>setProfile({...profile,[name]:e.target.value})} placeholder={placeholder}/></label>)}
          <label className="profile-wide">Career summary<textarea name="summary" value={String(profile.summary??"")} onChange={e=>setProfile({...profile,summary:e.target.value})} rows={4} maxLength={5000} placeholder="Tell employers what you do best..."/></label>
          <div className="profile-form-actions"><span>Sign-in email: {profile.email??""}</span></div>
        </div>
      </section>
      <section className="profile-section">
        <div className="profile-section-heading"><div><span className="section-kicker">YOUR NEXT MOVE</span><h2>Job preferences</h2><p>Use your preferences to personalize recommended roles.</p></div></div>
        <div className="profile-form profile-details preference-fields">
          <label className="profile-wide">Preferred roles<input name="preferred_roles" value={String(profile.preferred_roles??"")} onChange={e=>setProfile({...profile,preferred_roles:e.target.value})} placeholder="Product Designer, UX Researcher"/></label>
          <label>Work mode<select name="work_mode" value={String(profile.work_mode??"")} onChange={e=>setProfile({...profile,work_mode:e.target.value})}><option value="">Choose a work mode</option><option value="Remote">Remote</option><option value="Hybrid">Hybrid</option><option value="Onsite">On-site</option><option value="Flexible">Flexible</option></select></label>
          <label>Expected salary<input name="expected_salary" value={String(profile.expected_salary??"")} onChange={e=>setProfile({...profile,expected_salary:e.target.value})} placeholder="e.g. $100k–$130k"/></label>
          <label>Notice period<select name="notice_period" value={String(profile.notice_period??"")} onChange={e=>setProfile({...profile,notice_period:e.target.value})}><option value="">Choose a notice period</option><option>Immediate</option><option>2 weeks</option><option>1 month</option><option>2+ months</option></select></label>
        </div>
      </section>
    </form>
    <section className="profile-section">
      <div className="profile-section-heading"><div><span className="section-kicker">YOUR BACKGROUND</span><h2>Work experience</h2><p>Most recent roles appear first. Add details that show your impact.</p></div><button type="button" className="button button-outline profile-add" onClick={()=>{setAddingExperience(!addingExperience);setEditingExperience(null);}}><Plus size={16}/>{addingExperience?"Cancel":"Add experience"}</button></div>
      {addingExperience&&<ExperienceEditor onSave={value=>saveRecord("experience",value)} onCancel={()=>setAddingExperience(false)}/>}
      {experience.length===0&&!addingExperience?<div className="profile-empty"><BriefcaseBusiness size={20}/><span>No experience added yet. Add a role to highlight your work history.</span></div>:<div className="record-list">{experience.map(item=><article className="profile-record" key={item.id}>{editingExperience===item.id?<ExperienceEditor initial={item} onSave={value=>saveRecord("experience",value,item.id)} onCancel={()=>setEditingExperience(null)}/>:<><span className="record-icon"><BriefcaseBusiness size={18}/></span><div className="record-content"><h3>{item.title}</h3><p className="record-subtitle">{item.company}{item.location?` · ${item.location}`:""}</p><p className="record-dates"><CalendarDays size={14}/>{formatExperienceDate(item.start_date)} – {item.end_date?formatExperienceDate(item.end_date):"Present"}</p>{item.description&&<p className="record-description">{item.description}</p>}</div><div className="record-actions"><button type="button" className="record-action" onClick={()=>{setEditingExperience(item.id);setAddingExperience(false);}} aria-label={`Edit ${item.title}`}><Pencil size={15}/>Edit</button><button type="button" className="record-action record-delete" onClick={()=>void removeRecord("experience",item.id)} aria-label={`Remove ${item.title}`}><Trash2 size={15}/>Remove</button></div></>}</article>)}</div>}
    </section>
    <section className="profile-section">
      <div className="profile-section-heading"><div><span className="section-kicker">EDUCATION & TRAINING</span><h2>Education</h2><p>Your most recent education appears first.</p></div><button type="button" className="button button-outline profile-add" onClick={()=>{setAddingEducation(!addingEducation);setEditingEducation(null);}}><Plus size={16}/>{addingEducation?"Cancel":"Add education"}</button></div>
      {addingEducation&&<EducationEditor onSave={value=>saveRecord("education",value)} onCancel={()=>setAddingEducation(false)}/>}
      {education.length===0&&!addingEducation?<div className="profile-empty"><FileText size={20}/><span>No education added yet. Add a school, course, or qualification.</span></div>:<div className="record-list">{education.map(item=><article className="profile-record" key={item.id}>{editingEducation===item.id?<EducationEditor initial={item} onSave={value=>saveRecord("education",value,item.id)} onCancel={()=>setEditingEducation(null)}/>:<><span className="record-icon education-icon"><FileText size={18}/></span><div className="record-content"><h3>{item.institution}</h3><p className="record-subtitle">{[item.degree,item.field_of_study].filter(Boolean).join(" · ")||"Education"}</p><p className="record-dates"><CalendarDays size={14}/>{item.start_year||"—"} – {item.end_year||"Present"}</p></div><div className="record-actions"><button type="button" className="record-action" onClick={()=>{setEditingEducation(item.id);setAddingEducation(false);}} aria-label={`Edit education at ${item.institution}`}><Pencil size={15}/>Edit</button><button type="button" className="record-action record-delete" onClick={()=>void removeRecord("education",item.id)} aria-label={`Remove education at ${item.institution}`}><Trash2 size={15}/>Remove</button></div></>}</article>)}</div>}
    </section>
    <section className="profile-section resume-section"><div className="profile-section-heading"><div><span className="section-kicker">FOR EMPLOYERS</span><h2>Resume</h2><p>PDF or DOCX · Maximum file size 5 MB. Contact details are parsed automatically.</p></div></div>{profile.resume_path?<div className="resume-card"><div className="resume-file-icon"><FileText size={21}/></div><div className="resume-file-copy"><b>{profile.resume_filename||"Uploaded resume"}</b><p>Uploaded {profile.resume_uploaded_at?new Date(profile.resume_uploaded_at).toLocaleString():"just now"}</p></div><form className="resume-replace" onSubmit={e=>void upload(e)}><input name="file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required/><button className="button button-outline">Replace</button></form><button type="button" className="record-action record-delete" onClick={()=>void removeResume()}><Trash2 size={15}/>Remove</button><details className="resume-preview-details"><summary>Preview resume</summary><ResumeDocument profile={profile}/></details></div>:<form className="resume-form profile-resume" onSubmit={e=>void upload(e)}><FileText size={22}/><div><b>Add your resume</b><p>Upload a PDF or DOCX for a quick profile fill-in.</p></div><input name="file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required/><button className="button button-dark">Upload resume</button></form>}</section>
    <div className="profile-save-bar"><span>Save your personal details and job preferences.</span><button type="submit" form="profile-details-form" disabled={saving} className="button button-dark">{saving?"Saving…":"Save changes"} <Check size={16}/></button></div>
    <button className="text-link profile-back-bottom" onClick={onDone}>Back to dashboard <ArrowRight size={15}/></button>
  </main>;
}
function normalizeExperienceDate(value:string){return /^\d{4}-\d{2}$/.test(value)?`${value}-01`:value;}
function experienceSortDate(value:string){return value?normalizeExperienceDate(value):"9999-12-31";}
function calendarInputDate(value:string){return /^\d{4}-\d{2}$/.test(value)?`${value}-01`:value;}
function formatExperienceDate(value:string){const normalized=normalizeExperienceDate(value);if(!/^\d{4}-\d{2}-\d{2}$/.test(normalized))return value||"—";const [year,month,day]=normalized.split("-").map(Number);return new Intl.DateTimeFormat("en",{month:"short",year:"numeric",timeZone:"UTC"}).format(new Date(Date.UTC(year,month-1,day)));}
function EducationEditor({initial,onSave,onCancel}:{initial?:EducationEntry;onSave:(value:EducationInput)=>void;onCancel:()=>void}) {
  const [dateError,setDateError]=useState("");
  function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);const startDate=String(form.get("start_year")||"");const endDate=String(form.get("end_year")||"");const start=startDate?Number(startDate.slice(0,4)):null;const end=endDate?Number(endDate.slice(0,4)):null;if(start&&end&&end<start){setDateError("End year must be the same as or later than start year.");return;}setDateError("");void onSave({institution:String(form.get("institution")),degree:String(form.get("degree")||""),field_of_study:String(form.get("field_of_study")||""),start_year:start,end_year:end});}
  const maxDate=new Date().toISOString().slice(0,10);
  return <form className="record-editor" onSubmit={submit}><div className="editor-heading"><b>{initial?"Edit education":"Add education"}</b><span>Choose dates from the calendar; only the year is saved.</span></div><div className="editor-grid"><label>Institution *<input name="institution" required minLength={2} maxLength={200} defaultValue={initial?.institution??""} placeholder="School or institution"/></label><label>Degree<input name="degree" maxLength={160} defaultValue={initial?.degree??""} placeholder="e.g. Bachelor's degree"/></label><label>Field of study<input name="field_of_study" maxLength={160} defaultValue={initial?.field_of_study??""} placeholder="e.g. Computer science"/></label><label>Start date<input name="start_year" type="date" min="1950-01-01" max={maxDate} defaultValue={initial?.start_year?`${initial.start_year}-01-01`:""}/></label><label>End date<input name="end_year" type="date" min="1950-01-01" max={maxDate} defaultValue={initial?.end_year?`${initial.end_year}-01-01`:""}/></label></div>{dateError&&<p className="field-error" role="alert">{dateError}</p>}<div className="editor-actions"><button className="button button-dark">{initial?"Save education":"Add education"}</button><button type="button" className="button button-outline" onClick={onCancel}>Cancel</button></div></form>;
}
function ExperienceEditor({initial,onSave,onCancel}:{initial?:ExperienceEntry;onSave:(value:ExperienceInput)=>void;onCancel:()=>void}) {
  const [current,setCurrent]=useState(!initial?.end_date);
  const [dateError,setDateError]=useState("");
  function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);const start=String(form.get("start_date")||"");const end=current?"":String(form.get("end_date")||"");if(start&&end&&end<start){setDateError("End date must be the same as or later than start date.");return;}setDateError("");void onSave({company:String(form.get("company")),title:String(form.get("title")),location:String(form.get("location")||""),start_date:start,end_date:end,description:String(form.get("description")||"")});}
  return <form className="record-editor" onSubmit={submit}><div className="editor-heading"><b>{initial?"Edit experience":"Add experience"}</b><span>Pick dates from the calendar.</span></div><div className="editor-grid"><label>Job title *<input name="title" required minLength={2} maxLength={160} defaultValue={initial?.title??""} placeholder="e.g. Product Designer"/></label><label>Company *<input name="company" required minLength={2} maxLength={200} defaultValue={initial?.company??""} placeholder="Company name"/></label><label>Location<input name="location" maxLength={160} defaultValue={initial?.location??""} placeholder="City or remote"/></label><label>Start date<input name="start_date" type="date" min="1950-01-01" max={new Date().toISOString().slice(0,10)} defaultValue={calendarInputDate(initial?.start_date??"")}/></label><label>End date<input name="end_date" type="date" min="1950-01-01" max={new Date().toISOString().slice(0,10)} defaultValue={calendarInputDate(initial?.end_date??"")} disabled={current}/></label><label className="current-role"><input type="checkbox" checked={current} onChange={e=>setCurrent(e.target.checked)}/> I currently work here</label><label className="editor-wide">Description<textarea name="description" rows={3} maxLength={4000} defaultValue={initial?.description??""} placeholder="Share your responsibilities and achievements."/></label></div>{dateError&&<p className="field-error" role="alert">{dateError}</p>}<div className="editor-actions"><button className="button button-dark">{initial?"Save experience":"Add experience"}</button><button type="button" className="button button-outline" onClick={onCancel}>Cancel</button></div></form>;
}
function Footer({onNavigate}:{onNavigate:(s:string)=>void}) {return <footer className="footer"><div className="brand"><span className="brand-mark">RR</span><span>Role<span className="brand-light">Rise</span></span></div><p>Good people. Great places. Better work ahead.</p><div><button onClick={()=>onNavigate("jobs")}>Find jobs</button><button onClick={()=>onNavigate("register")}>Create account</button></div><small>© 2026 RoleRise. Made for your next chapter.</small></footer>;}
