import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="🚢 运费计算器", layout="wide", page_icon="📦")

# ====================== 数据加载 ======================
def load_prices():
    file_path = 'prices.csv'
    if not os.path.exists(file_path):
        columns = ['渠道名称', '国家', '仓库', '运输方式', '计价类型',
                   '每立方价格_元_per_cbm', '重量单价_元_per_kg',
                   '预估时效', '生效日期', '固定费_元', '报关费_元']
        pd.DataFrame(columns=columns).to_csv(file_path, index=False, encoding='utf-8-sig')
        return pd.DataFrame(columns=columns)
    
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    df.columns = [col.strip().replace(' ', '').replace('\ufeff', '') for col in df.columns]
    
    col_map = {col: col for col in df.columns}
    for col in df.columns:
        if '国家' in col or '目的国' in col: col_map[col] = '国家'
        elif '仓库' in col or '目的港' in col: col_map[col] = '仓库'
        elif '渠道' in col: col_map[col] = '渠道名称'
        elif '运输方式' in col: col_map[col] = '运输方式'
        elif '计价类型' in col: col_map[col] = '计价类型'
        elif '每立方' in col or '体积单价' in col: col_map[col] = '每立方价格_元_per_cbm'
        elif '重量单价' in col or '元_per_kg' in col: col_map[col] = '重量单价_元_per_kg'
        elif '时效' in col: col_map[col] = '预估时效'
        elif '生效日期' in col: col_map[col] = '生效日期'
        elif '固定费' in col: col_map[col] = '固定费_元'
        elif '报关费' in col: col_map[col] = '报关费_元'
    df = df.rename(columns=col_map)
    
    for col in ['国家', '仓库', '每立方价格_元_per_cbm', '重量单价_元_per_kg', '固定费_元', '报关费_元']:
        if col not in df.columns:
            df[col] = '' if col in ['国家', '仓库'] else 0.0
    
    required = ['国家', '仓库', '渠道名称', '运输方式', '计价类型']
    for r in required:
        if r not in df.columns:
            df[r] = ''
    df['国家'] = df['国家'].astype(str).str.strip()
    df['仓库'] = df['仓库'].astype(str).str.strip()
    return df

def calculate_total_freight(rule, vol_m3, weight_kg):
    ptype = str(rule.get('计价类型', '')).strip()
    if ptype == "体积计价":
        price = pd.to_numeric(rule.get('每立方价格_元_per_cbm'), errors='coerce')
        if pd.isna(price) or price <= 0: return None, "❌ 体积计价缺少单价"
        freight = vol_m3 * price
        detail = f"体积计价：{vol_m3:.3f} m³ × {price} 元/m³ = {freight:.2f} 元"
    elif ptype == "重量计价":
        price = pd.to_numeric(rule.get('重量单价_元_per_kg'), errors='coerce')
        if pd.isna(price) or price <= 0: return None, "❌ 重量计价缺少单价"
        freight = weight_kg * price
        detail = f"重量计价：{weight_kg:.1f} kg × {price} 元/kg = {freight:.2f} 元"
    else:
        return None, f"❌ 未知计价类型：{ptype}"
    return round(freight, 2), detail

# ====================== 主页面 ======================
page = st.sidebar.selectbox("🧭 导航", ["前台 - 运费计算器", "后台 - 价格规则管理"])

if page == "前台 - 运费计算器":
    st.title("🚢 运费计算器 - 一键比价")
    df = load_prices()
    if df.empty or df['国家'].dropna().empty:
        st.error("请先到后台添加渠道价格数据")
        st.stop()
    
    # 国家 + 仓库级联筛选（保持不变）
    country_options = sorted([c for c in df['国家'].unique() if str(c).strip() != ''])
    selected_countries = st.multiselect("🌍 国家（可选）", options=country_options, default=country_options[:1] if country_options else [])
    
    if selected_countries:
        filtered_warehouses = df[df['国家'].isin(selected_countries)]['仓库'].unique()
    else:
        filtered_warehouses = df['仓库'].unique()
    warehouse_options = sorted([w for w in filtered_warehouses if str(w).strip() != ''])
    selected_warehouses = st.multiselect("🏬 仓库（核心选择，可多选）", options=warehouse_options, default=warehouse_options[:1] if warehouse_options else [])
    
    # 货物信息（保持不变）
    st.subheader("📦 货物信息")
    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("产品名称", "标准产品A")
        total_products = st.number_input("总数量（件）【产品总件数】", min_value=1, value=1000)
        total_cartons = st.number_input("总箱数（卡通箱）", min_value=1, value=100)
    with col2:
        total_vol_m3 = st.number_input("总体积（m³）", min_value=0.0, value=1.0, step=0.01)
        total_weight_kg = st.number_input("总毛重（kg）", min_value=0.0, value=200.0, step=0.1)
    
    avg_pcs = round(total_products / total_cartons, 2) if total_cartons > 0 else 0
    st.success(f"✅ 总数量 = {total_products} 件 | 总箱数 = {total_cartons} 箱 | 平均每箱 {avg_pcs} 件 | 总体积 = {total_vol_m3:.3f} m³ | 总毛重 = {total_weight_kg:.1f} kg")
    
    # 成本信息（含 AWD 配置费，保持不变）
    st.subheader("💰 成本信息（关税 + Inbound + AWD 配置费）")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        purchase_price = st.number_input("产品采购价 (RMB/件)", value=100.0)
        tariff_rate = st.number_input("目的国关税率 (%)", value=0.0)
    with col_b:
        inbound_wc = st.number_input("Inbound WC (RMB/件)", value=0.0)
        inbound_ec = st.number_input("Inbound EC (RMB/件)", value=0.0)
    with col_c:
        awd_per_carton = st.number_input("AWD 每箱配置费 (RMB/箱)", value=19.0)
        awd_per_cuft = st.number_input("AWD 每立方英尺配置费 (RMB/cu ft)", value=9.0)
        st.caption("※ 仅当渠道名称包含 “AWD” 时生效（1 m³ = 35.3147 cu ft）")
    
    total_purchase = purchase_price * total_products
    tariff_total = total_purchase * (tariff_rate / 100)
    inbound_total = (inbound_wc + inbound_ec) * total_products
    st.info(f"**公共成本**：采购 {total_purchase:,.2f} | 关税 {tariff_total:,.2f} | Inbound {inbound_total:,.2f}")
    
    filtered = df[(df['国家'].isin(selected_countries) if selected_countries else True) & (df['仓库'].isin(selected_warehouses))]
    
    # ====================== 整批计算（单渠道） ======================
    st.subheader("📊 整批计算（单渠道）")
    channel_options = sorted(filtered['渠道名称'].unique()) if not filtered.empty else []
    selected_channels = st.multiselect("🚢 指定渠道（不选则默认计算所选仓库下的所有渠道）", options=channel_options)
    
    if st.button("🚀 计算整批方案", type="primary", use_container_width=True):
        results = []
        channels_to_use = selected_channels if selected_channels else filtered['渠道名称'].unique()
        for ch in channels_to_use:
            rule = filtered[filtered['渠道名称'] == ch].iloc[0]
            freight_total, detail = calculate_total_freight(rule, total_vol_m3, total_weight_kg)
            if freight_total is None: continue
            
            awd_fee = 0.0
            if "AWD" in ch.upper():
                cuft = total_vol_m3 * 35.3147
                awd_fee = (awd_per_carton * total_cartons) + (awd_per_cuft * cuft)
                detail += f"\nAWD 配置费 = {awd_fee:.2f} 元（{total_cartons}箱 + {cuft:.1f} cu ft）"
            
            fixed = pd.to_numeric(rule.get('固定费_元', 0), errors='coerce') or 0
            customs = pd.to_numeric(rule.get('报关费_元', 0), errors='coerce') or 0
            total_fixed = fixed + customs + awd_fee
            
            full_landed = freight_total + tariff_total + inbound_total + total_fixed
            freight_per = round(freight_total / total_products, 2) if total_products > 0 else 0
            landed_per = round(full_landed / total_products, 2) if total_products > 0 else 0
            
            results.append({
                "方案类型": "单渠道整批",
                "国家": rule.get('国家', ''), "仓库": rule.get('仓库', ''),
                "渠道名称": ch, "运输方式": rule.get('运输方式', ''),
                "预估运费": f"总 {freight_total:.2f} | 单 {freight_per:.2f}",
                "预估时效": rule.get('预估时效', ''),
                "推荐": "", "总落地成本 (元)": round(full_landed, 2),
                "单件落地成本 (元/件)": landed_per,
                "计算明细": detail,
                "总运费": freight_total
            })
        if results:
            results = sorted(results, key=lambda x: x["总运费"])
            st.session_state['single_results'] = results
            st.success("✅ 整批方案已计算完成")
        else:
            st.warning("暂无可用渠道")
    
    # ====================== 分批计算 ======================
    st.subheader("🧩 分批计算（每个仓库单独绑定渠道 + 箱数）")
    if len(selected_warehouses) > 0:
        st.write("**为每个仓库指定渠道和分配箱数**（总和必须等于总箱数）")
        split_alloc = {}
        total_alloc = 0
        for idx, warehouse in enumerate(selected_warehouses):
            col1, col2, col3 = st.columns([3, 3, 2])
            with col1:
                avail_channels = filtered[filtered['仓库'] == warehouse]['渠道名称'].unique()
                ch = st.selectbox(f"仓库 {warehouse} 的渠道", options=avail_channels, key=f"split_ch_{idx}")
            with col2:
                boxes = st.number_input(f"分配箱数", min_value=0, value=0, step=1, key=f"split_box_{idx}")
            with col3:
                st.write(f"（共 {total_cartons} 箱）")
            
            split_alloc[warehouse] = {"channel": ch, "boxes": boxes}
            total_alloc += boxes
        
        if total_alloc != total_cartons:
            st.error(f"⚠️ 已分配箱数总和 = {total_alloc} 箱（必须等于总箱数 {total_cartons} 箱）")
        else:
            if st.button("🚀 计算分批方案", type="primary", use_container_width=True):
                total_freight = 0.0
                total_fixed = 0.0
                detail_lines = []
                
                for warehouse, info in split_alloc.items():
                    if info["boxes"] == 0: continue
                    rule = filtered[(filtered['仓库'] == warehouse) & (filtered['渠道名称'] == info["channel"])].iloc[0]
                    ratio = info["boxes"] / total_cartons
                    alloc_vol = total_vol_m3 * ratio
                    alloc_weight = total_weight_kg * ratio
                    
                    freight, detail = calculate_total_freight(rule, alloc_vol, alloc_weight)
                    if freight is None: continue
                    
                    awd_fee = 0.0
                    if "AWD" in info["channel"].upper():
                        cuft = alloc_vol * 35.3147
                        awd_fee = (awd_per_carton * info["boxes"]) + (awd_per_cuft * cuft)
                        detail += f"\nAWD 配置费 = {awd_fee:.2f} 元（{info['boxes']}箱 + {cuft:.1f} cu ft）"
                    
                    fixed = pd.to_numeric(rule.get('固定费_元', 0), errors='coerce') or 0
                    customs = pd.to_numeric(rule.get('报关费_元', 0), errors='coerce') or 0
                    
                    total_freight += freight
                    total_fixed += (fixed + customs + awd_fee)
                    detail_lines.append(f"{warehouse} → {info['channel']}（{info['boxes']}箱）：{detail}")
                
                full_landed = total_freight + tariff_total + inbound_total + total_fixed
                freight_per = round(total_freight / total_products, 2) if total_products > 0 else 0
                landed_per = round(full_landed / total_products, 2) if total_products > 0 else 0
                
                st.session_state['multi_result'] = {
                    "方案类型": "🧩 多渠道分批",
                    "国家": "—", "仓库": "—",
                    "渠道名称": "多仓库分批组合",
                    "运输方式": "—",
                    "预估运费": f"总 {total_freight:.2f} | 单 {freight_per:.2f}",
                    "预估时效": "—",
                    "推荐": "分批方案",
                    "总落地成本 (元)": round(full_landed, 2),
                    "单件落地成本 (元/件)": landed_per,
                    "计算明细": "\n".join(detail_lines) + f"\n固定费+报关费+AWD配置费总计 = {total_fixed:.2f} 元",
                    "总运费": total_freight
                }
                st.success("✅ 分批方案已计算完成")
    
    # ====================== 最终比价对比结果（全局推荐修复） ======================
    st.subheader("📊 最终比价对比结果")
    combined = []
    if 'single_results' in st.session_state:
        combined.extend(st.session_state['single_results'])
    if 'multi_result' in st.session_state:
        combined.append(st.session_state['multi_result'])
    
    if combined:
        result_df = pd.DataFrame(combined)
        # 全局按总落地成本排序（最关键修复）
        result_df = result_df.sort_values(by="总落地成本 (元)", ascending=True)
        
        # 全局标记最便宜方案
        min_landed = result_df["总落地成本 (元)"].min()
        result_df["推荐"] = result_df["总落地成本 (元)"].apply(lambda x: "✅ 最便宜" if x == min_landed else "")
        
        st.dataframe(
            result_df[['方案类型', '国家', '仓库', '渠道名称', '运输方式', '预估运费', '预估时效', 
                       '推荐', '总落地成本 (元)', '单件落地成本 (元/件)', '计算明细']],
            use_container_width=True, hide_index=True
        )
        
        st.download_button(
            "📤 导出完整对比结果 CSV",
            data=result_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"运费比价对比_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    else:
        st.info("👉 请先在上方计算整批方案或分批方案，结果会自动出现在这里")
    
    st.caption("本地运费计算器 | 已全局按总落地成本标记最便宜方案 | 数据保存在 prices.csv")

else:  # 后台
    st.title("🔧 后台 - 价格规则管理")
    password = st.text_input("管理员密码", type="password")
    if password == "admin123":
        st.success("✅ 已进入后台")
        df = load_prices()
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存到文件", type="primary"):
                edited_df.to_csv('prices.csv', index=False, encoding='utf-8-sig')
                st.success("✅ 保存成功！")
                st.rerun()
        with col2:
            uploaded = st.file_uploader("📥 导入 CSV 文件", type="csv")
            if uploaded:
                pd.read_csv(uploaded, encoding='utf-8-sig').to_csv('prices.csv', index=False, encoding='utf-8-sig')
                st.success("✅ 导入成功")
                st.rerun()
    else:
        if password:
            st.error("密码错误")

st.caption("© 内部运费工具 | 推荐标签已全局修正")