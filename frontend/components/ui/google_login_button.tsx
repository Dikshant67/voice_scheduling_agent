"use client";

import { useUser } from "@/app/context/UserContext";
import { GoogleLogin, CredentialResponse } from "@react-oauth/google";
import jwt_decode from "jwt-decode";
import { useRouter } from "next/navigation";
import { ReactNode, useState } from "react";
import { ChevronDownIcon } from "@heroicons/react/24/solid";
// Define the expected shape of the decoded JWT payload
interface DecodedJWT {
  name: string;
  email: string;
  picture: string;
  [key: string]: any;
}

interface GoogleLoginButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: string;
  children: ReactNode;
}

export default function GoogleLoginButton({
  children,
  className,
  size,
  ...props
}: GoogleLoginButtonProps) {
  const router = useRouter();
  const { user, setUser } = useUser();
  const [isMenuOpen, setIsMenuOpen] = useState(false); // State for accordion menu

  const handleSuccess = (credentialResponse: CredentialResponse) => {
    if (credentialResponse.credential) {
      const decoded: DecodedJWT = jwt_decode(credentialResponse.credential);
      if (decoded.name && decoded.email && decoded.picture) {
        const userData = {
          name: decoded.name,
          email: decoded.email,
          picture: decoded.picture,
        };
        setUser(userData);
        // router.push("/dashboard");
        console.log("✅ User Info:", userData);
      } else {
        console.error("❌ Invalid user data in JWT");
      }
    } else {
      console.error("❌ Login failed: No credential returned");
    }
  };

  const handleError = () => {
    console.error("❌ Google login error");
  };

  const handleLogout = () => {
    setUser(null); // Clear user from context
    router.push("/"); // Redirect to home or login page
    setIsMenuOpen(false); // Close menu on logout
  };

  const handleProfileClick = () => {
    router.push("/profile"); // Redirect to profile page
    setIsMenuOpen(false); // Close menu
  };

  // Conditional rendering: Show user profile with accordion menu if logged in, otherwise show Google login
  if (user) {
    return (
      <div className="relative flex items-center gap-3">
        <img
          src={user.picture}
          alt="Profile"
          className="w-8 h-8 rounded-full cursor-pointer"
        />
        <div className="flex items-center gap-1">
          <span className="font-medium">{user.name}</span>
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="text-sm text-gray-600 hover:text-gray-800 focus:outline-none"
            aria-label={isMenuOpen ? "Close menu" : "Open menu"}
          >
            <ChevronDownIcon className="w-4 h-4" />
          </button>
        </div>
        <div
          className={`absolute top-full mt-2 right-0 bg-white shadow-lg rounded-md overflow-hidden transition-all duration-300 ease-in-out ${
            isMenuOpen ? "max-h-40 opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <button
            onClick={handleProfileClick}
            className="block w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 text-left"
          >
            Profile
          </button>
          <button
            onClick={handleLogout}
            className="block w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 text-left"
          >
            Logout
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <GoogleLogin
        onSuccess={handleSuccess}
        onError={handleError}
        // size={size || "medium"}
        text="signin_with"
        logo_alignment="left"
      />
      {children && <span>{children}</span>}
    </div>
  );
}
// "use client";

// import { useUser } from "@/app/context/UserContext";
// import { GoogleLogin, CredentialResponse } from "@react-oauth/google";
// import jwt_decode from "jwt-decode";
// import { useRouter } from "next/navigation";
// import { ReactNode, useState } from "react";

// // Define the expected shape of the decoded JWT payload
// interface DecodedJWT {
//   name: string;
//   email: string;
//   picture: string;
//   [key: string]: any;
// }

// interface GoogleLoginButtonProps
//   extends React.ButtonHTMLAttributes<HTMLButtonElement> {
//   size?: string;
//   children: ReactNode;
// }

// export default function GoogleLoginButton({
//   children,
//   className,
//   size,
//   ...props
// }: GoogleLoginButtonProps) {
//   const router = useRouter();
//   const { user, setUser } = useUser();
//   const [isDropdownOpen, setIsDropdownOpen] = useState(false); // State for dropdown visibility

//   const handleSuccess = (credentialResponse: CredentialResponse) => {
//     if (credentialResponse.credential) {
//       const decoded: DecodedJWT = jwt_decode(credentialResponse.credential);
//       if (decoded.name && decoded.email && decoded.picture) {
//         const userData = {
//           name: decoded.name,
//           email: decoded.email,
//           picture: decoded.picture,
//         };
//         setUser(userData);
//         router.push("/dashboard");
//         console.log("✅ User Info:", userData);
//       } else {
//         console.error("❌ Invalid user data in JWT");
//       }
//     } else {
//       console.error("❌ Login failed: No credential returned");
//     }
//   };

//   const handleError = () => {
//     console.error("❌ Google login error");
//   };

//   const handleLogout = () => {
//     setUser(null); // Clear user from context
//     router.push("/"); // Redirect to home or login page
//   };

//   // Conditional rendering: Show user profile with dropdown if logged in, otherwise show Google login
//   if (user) {
//     return (
//       <div
//         className="relative flex items-center gap-3"
//         onMouseEnter={() => setIsDropdownOpen(true)}
//         onMouseLeave={() => setIsDropdownOpen(false)}
//       >
//         <img
//           src={user.picture}
//           alt="Profile"
//           className="w-8 h-8 rounded-full cursor-pointer"
//         />
//         <span className="font-medium cursor-pointer">{user.name}</span>
//         {isDropdownOpen && (
//           <div className="absolute top-full mt-2 right-0 bg-white shadow-lg rounded-md py-2 z-10">
//             <button
//               onClick={handleLogout}
//               className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
//             >
//               Logout
//             </button>
//           </div>
//         )}
//       </div>
//     );
//   }

//   return (
//     <div className={className}>
//       <GoogleLogin
//         onSuccess={handleSuccess}
//         onError={handleError}
//         // size={size || "medium"}
//         text="signin_with"
//         logo_alignment="left"
//       />
//       {children && <span>{children}</span>}
//     </div>
//   );
// }
// // "use client";

// // import { useUser } from "@/app/context/UserContext";
// // import { GoogleLogin, CredentialResponse } from "@react-oauth/google";
// // import jwt_decode from "jwt-decode";
// // import { useRouter } from "next/navigation";
// // import { ReactNode } from "react";

// // // Define the expected shape of the decoded JWT payload
// // interface DecodedJWT {
// //   name: string;
// //   email: string;
// //   picture: string;
// //   [key: string]: any; // For other potential fields in the JWT
// // }

// // interface GoogleLoginButtonProps
// //   extends React.ButtonHTMLAttributes<HTMLButtonElement> {
// //   size?: string;
// //   children: ReactNode;
// // }

// // export default function GoogleLoginButton({
// //   children,
// //   className,
// //   size,
// //   ...props
// // }: GoogleLoginButtonProps) {
// //   const router = useRouter();
// //   const { user, setUser } = useUser();

// //   const handleSuccess = (credentialResponse: CredentialResponse) => {
// //     if (credentialResponse.credential) {
// //       const decoded: DecodedJWT = jwt_decode(credentialResponse.credential);
// //       if (decoded.name && decoded.email && decoded.picture) {
// //         const userData = {
// //           name: decoded.name,
// //           email: decoded.email,
// //           picture: decoded.picture,
// //         };
// //         setUser(userData); // Set user in context
// //         // router.push("/dashboard"); // Redirect to dashboard
// //         console.log("✅ User Info:", userData);
// //       } else {
// //         console.error("❌ Invalid user data in JWT");
// //       }
// //     } else {
// //       console.error("❌ Login failed: No credential returned");
// //     }
// //   };

// //   const handleError = () => {
// //     console.error("❌ Google login error");
// //   };

// //   // Conditional rendering: Show user profile if logged in, otherwise show Google login
// //   if (user) {
// //     return (
// //       <div className="flex items-center gap-3">
// //         <img
// //           src={user.picture}
// //           alt="Profile"
// //           className="w-8 h-8 rounded-full"
// //         />
// //         <span className="font-medium">{user.name}</span>
// //       </div>
// //     );
// //   }

// //   return (
// //     <div className={className}>
// //       {/* Render GoogleLogin directly, not inside a button */}
// //       <GoogleLogin
// //         onSuccess={handleSuccess}
// //         onError={handleError}
// //         // size={size || "medium"} // Use size prop or default to medium
// //         text="signin_with" // Customize button text (e.g., "Sign in with Google")
// //         logo_alignment="left" // Optional: Align Google logo
// //       />
// //       {/* If you want to include children, render them separately */}
// //       {children && <span>{children}</span>}
// //     </div>
// //   );
// // }
// // "use client";

// // import { useUser } from "@/app/context/UserContext";
// // import { GoogleLogin, CredentialResponse } from "@react-oauth/google";
// // import jwt_decode, { JwtPayload } from "jwt-decode";
// // import { useRouter } from "next/navigation";
// // import { ReactNode } from "react";
// // interface GoogleLoginButtonProps
// //   extends React.ButtonHTMLAttributes<HTMLButtonElement> {
// //   size?: string;
// //   children: React.ReactNode;
// // }
// // export default function GoogleLoginButton({
// //   children,
// //   className,
// //   size,
// //   ...props
// // }: GoogleLoginButtonProps) {
// //   const router = useRouter();
// //   const { user, setUser } = useUser();
// //   const handleSuccess = (credentialResponse: CredentialResponse) => {
// //     if (credentialResponse.credential) {
// //       const decoded: any = jwt_decode(credentialResponse.credential);
// //       const userData = {
// //         name: decoded.name,
// //         email: decoded.email,
// //         picture: decoded.picture,
// //       };
// //       setUser(userData); // Set to context
// //       router.push("/dashboard"); // Redirect after login
// //       console.log("✅ User Info:", decoded);
// //       // You can now use decoded.email, decoded.name, decoded.picture, etc.
// //       if (decoded.name && decoded.email && decoded.picture) {
// //         setUser({
// //           name: decoded.name,
// //           email: decoded.email,
// //           picture: decoded.picture,
// //         });
// //       }
// //     } else {
// //       console.error("❌ Login failed: No credential returned");
// //     }
// //   };

// //   const handleError = () => {
// //     console.error("❌ Google login error");
// //   };
// //   if (user) {
// //     return (
// //       <div className="flex items-center gap-3">
// //         <img
// //           src={user.picture}
// //           alt="Profile"
// //           className="w-8 h-8 rounded-full"
// //         />
// //         <span className="font-medium">{user.name}</span>
// //       </div>
// //     );
// //   }
// //   return (
// //     <div>
// //       <button className={className} {...props}>
// //         {children}{" "}
// //         <GoogleLogin
// //           onSuccess={handleSuccess}
// //           onError={handleError}
// //         ></GoogleLogin>
// //       </button>
// //     </div>
// //   );
// // }
