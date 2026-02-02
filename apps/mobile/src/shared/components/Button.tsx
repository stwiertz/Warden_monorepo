import React from "react";
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  type TouchableOpacityProps,
} from "react-native";

interface ButtonProps extends TouchableOpacityProps {
  title: string;
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
}

export function Button({
  title,
  variant = "primary",
  loading = false,
  disabled,
  className,
  ...props
}: ButtonProps) {
  const baseClasses = "min-h-[44px] min-w-[44px] rounded-lg px-6 py-3 items-center justify-center";
  const variantClasses = {
    primary: "bg-accent",
    secondary: "bg-surface border border-text-secondary",
    ghost: "bg-transparent",
  };
  const textVariantClasses = {
    primary: "text-white font-semibold text-body",
    secondary: "text-text-primary font-semibold text-body",
    ghost: "text-accent font-semibold text-body",
  };
  const disabledClass = disabled || loading ? "opacity-50" : "";

  return (
    <TouchableOpacity
      className={`${baseClasses} ${variantClasses[variant]} ${disabledClass} ${className ?? ""}`}
      disabled={disabled || loading}
      activeOpacity={0.7}
      {...props}
    >
      {loading ? (
        <ActivityIndicator color={variant === "primary" ? "#FFFFFF" : "#FF6B00"} />
      ) : (
        <Text className={textVariantClasses[variant]}>{title}</Text>
      )}
    </TouchableOpacity>
  );
}
