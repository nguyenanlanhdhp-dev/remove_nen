import streamlit as st
from PIL import Image, ImageEnhance
from rembg import remove
import cv2
import numpy as np

# Cấu hình trang web
st.set_page_config(page_title="Studio Ảnh Thẻ Di Động", page_icon="📸", layout="centered")

st.title("📸 Studio Ảnh Thẻ & Tách Nền AI")
st.write("Chụp hoặc tải ảnh lên để tách nền, làm đẹp và tạo ảnh thẻ chuẩn ngay trên điện thoại/máy tính!")

# --- THANH CÔNG CỤ BÊN TRÁI (HOẶC PHÍA TRÊN TRÊN ĐIỆN THOẠI) ---
st.sidebar.header("⚙️ Tùy Chọn Xử Lý")

# Chọn cỡ thẻ
card_type = st.sidebar.selectbox("Chọn kích thước ảnh thẻ:", ["3x4 cm", "4x6 cm"])

# Chọn màu nền hoặc trong suốt
use_transparent = st.sidebar.checkbox("Giữ nền trong suốt (Transparent PNG)", value=True)
bg_color = None
if not use_transparent:
    picker_color = st.sidebar.color_picker("Chọn màu nền ảnh thẻ", "#FFFFFF")
    # Chuyển mã Hex sang RGB tuple
    hex_code = picker_color.lstrip('#')
    rgb_tuple = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    bg_color = (rgb_tuple[0], rgb_tuple[1], rgb_tuple[2], 255)

# Thanh trượt tinh chỉnh thủ công
st.sidebar.subheader("Tinh chỉnh ánh sáng")
brightness = st.sidebar.slider("Độ sáng", 0.5, 1.5, 1.0, 0.05)
contrast = st.sidebar.slider("Độ tương phản", 0.5, 1.5, 1.0, 0.05)

# --- KHU VỰC TẢI ẢNH LÊN ---
uploaded_file = st.file_uploader("📂 Tải ảnh gốc lên (hoặc chụp trực tiếp bằng camera điện thoại):", type=["jpg", "jpeg", "png", "webp"])

def smart_crop_portrait(pil_img, target_ratio=3/4):
    w, h = pil_img.size
    if w / h > target_ratio:
        crop_h = h
        crop_w = int(crop_h * target_ratio)
    else:
        crop_w = w
        crop_h = int(crop_w / target_ratio)
        if crop_h > h:
            crop_h = h
            crop_w = int(crop_h * target_ratio)

    left = (w - crop_w) // 2
    top = int((h - crop_h) * 0.2)
    top = max(0, top)
    if top + crop_h > h:
        top = h - crop_h

    return pil_img.crop((left, top, left + crop_w, top + crop_h))

def beautify_face(pil_img):
    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)
    balanced_img = cv2.cvtColor(cv2.merge((l_clahe, a, b)), cv2.COLOR_LAB2BGR)

    smoothed_skin = cv2.bilateralFilter(balanced_img, d=5, sigmaColor=25, sigmaSpace=25)
    final_bgr = cv2.addWeighted(smoothed_skin, 0.2, balanced_img, 0.8, 0)

    beautified_pil = Image.fromarray(cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB))
    sharpness_enhancer = ImageEnhance.Sharpness(beautified_pil)
    return sharpness_enhancer.enhance(1.8)

if uploaded_file is not None:
    original_image = Image.open(uploaded_file).convert("RGBA")

    st.subheader("🖼️ Ảnh Gốc:")
    st.image(original_image, use_container_width=True)

    if st.button("🚀 Xử Lý Ảnh Ngay", type="primary"):
        with st.spinner("Đang tách nền AI và tối ưu độ nét cao..."):
            try:
                # 1. Tách nền AI
                output_img = remove(original_image, alpha_matting=False)

                data = np.array(output_img)
                r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
                a[a < 220] = 0
                cleaned_data = np.stack([r, g, b, a], axis=-1)
                subject_rgba = Image.fromarray(cleaned_data, mode="RGBA")

                # 2. Cắt khung thông minh
                target_ratio = 3/4 if "3x4" in card_type else 2/3
                cropped_subject = smart_crop_portrait(subject_rgba, target_ratio)

                subject_rgb = cropped_subject.convert("RGB")
                subject_alpha = cropped_subject.split()[3]

                # 3. Làm đẹp & tăng sắc nét
                beautified_rgb = beautify_face(subject_rgb)

                # 4. Tùy chỉnh ánh sáng thủ công
                enhancer_b = ImageEnhance.Brightness(beautified_rgb)
                beautified_rgb = enhancer_b.enhance(brightness)
                enhancer_c = ImageEnhance.Contrast(beautified_rgb)
                beautified_rgb = enhancer_c.enhance(contrast)

                # 5. Ghép nền
                subject_rgba_final = beautified_rgb.convert("RGBA")
                subject_rgba_final.putalpha(subject_alpha)

                if bg_color is None:
                    final_result = subject_rgba_final
                else:
                    background = Image.new("RGBA", beautified_rgb.size, bg_color)
                    combined = Image.alpha_composite(background, subject_rgba_final)
                    final_result = combined.convert("RGB")

                # Lưu vào session_state để hiển thị và tải về
                st.session_state["final_result"] = final_result
                st.success("✨ Xử lý thành công!")

            except Exception as e:
                st.error(f"Đã xảy ra lỗi: {str(e)}")

    # Hiển thị kết quả nếu đã xử lý xong
    if "final_result" in st.session_state:
        st.subheader("✨ Kết Quả Xử Lý:")
        st.image(st.session_state["final_result"], use_container_width=True)

        # Nút tải ảnh về
        file_extension = "png" if bg_color is None and use_transparent else "jpg"
        mime_type = "image/png" if file_extension == "png" else "image/jpeg"

        # Chuyển đổi ảnh sang bytes để cho phép nút tải về hoạt động
        import io
        buf = io.BytesIO()
        if file_extension == "png":
            st.session_state["final_result"].save(buf, format="PNG")
        else:
            st.session_state["final_result"].save(buf, format="JPEG", quality=95)

        byte_im = buf.getvalue()

        st.download_button(
            label=f"📥 Tải Ảnh Xuống ({file_extension.upper()} Chất Lượng Cao)",
            data=byte_im,
            file_name=f"anh_the_hd.{file_extension}",
            mime=mime_type
        )
